"""Data update coordinator for HLK-DIO16."""

from __future__ import annotations

from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import HlkDio16Client
from .const import AVAILABILITY_GRACE_SECONDS, SCAN_INTERVAL_SECONDS
from .exceptions import HlkDio16Error
from .reconnect import ReconnectPolicy

_LOGGER = logging.getLogger(__name__)


class HlkDio16Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll digital inputs and outputs; self-heal the TCP session on failure."""

    def __init__(self, hass: HomeAssistant, client: HlkDio16Client) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"HLK-DIO16 {client.host}",
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client
        self._reconnect = ReconnectPolicy()
        self._last_success_mono: float | None = None

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if not self.client.connected:
                await self.client.connect()
            inputs = await self.client.read_inputs()
            outputs = await self.client.read_outputs()
        except HlkDio16Error as err:
            return await self._async_handle_failure(err)

        prior_failures = self._reconnect.failures
        self._apply_interval(self._reconnect.on_success())
        self._last_success_mono = time.monotonic()
        if prior_failures:
            _LOGGER.warning(
                "HLK-DIO16 %s:%s recovered after %s failure(s)",
                self.client.host,
                self.client.port,
                prior_failures,
            )
        return {"inputs": inputs, "outputs": outputs}

    async def async_set_output(self, channel: int, state: bool) -> None:
        """Set an output and refresh coordinator data."""
        try:
            outputs = await self.client.set_output(channel, state)
            inputs = (self.data or {}).get("inputs") or await self.client.read_inputs()
        except HlkDio16Error as err:
            await self._async_note_failure(err)
            raise UpdateFailed(str(err)) from err

        self._apply_interval(self._reconnect.on_success())
        self._last_success_mono = time.monotonic()
        self.async_set_updated_data({"inputs": inputs, "outputs": outputs})

    async def _async_handle_failure(self, err: HlkDio16Error) -> dict[str, Any]:
        """Drop the socket, back off, and keep last data during a short grace."""
        await self._async_note_failure(err)
        if self._within_grace() and isinstance(self.data, dict):
            _LOGGER.debug(
                "HLK-DIO16 %s:%s serving last-known state during grace",
                self.client.host,
                self.client.port,
            )
            return self.data
        raise UpdateFailed(str(err)) from err

    async def _async_note_failure(self, err: HlkDio16Error) -> None:
        delay, force_reset = self._reconnect.on_failure()
        self._apply_interval(delay)
        await self.client.disconnect()
        if force_reset:
            _LOGGER.warning(
                "HLK-DIO16 %s:%s unreachable (%s); forced reset, retry in %.1fs",
                self.client.host,
                self.client.port,
                err,
                delay,
            )
        else:
            _LOGGER.warning(
                "HLK-DIO16 %s:%s unreachable (%s); retry in %.1fs",
                self.client.host,
                self.client.port,
                err,
                delay,
            )

    def _within_grace(self) -> bool:
        if self._last_success_mono is None or not self.data:
            return False
        return (time.monotonic() - self._last_success_mono) <= AVAILABILITY_GRACE_SECONDS

    def _apply_interval(self, seconds: float) -> None:
        new_interval = timedelta(seconds=seconds)
        if self.update_interval != new_interval:
            self.update_interval = new_interval
