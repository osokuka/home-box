"""Data update coordinator for HLK-DIO16."""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .client import HlkDio16Client
from .const import SCAN_INTERVAL_SECONDS
from .exceptions import HlkDio16Error

_LOGGER = logging.getLogger(__name__)


class HlkDio16Coordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Poll digital inputs and outputs over the persistent TCP client."""

    def __init__(self, hass: HomeAssistant, client: HlkDio16Client) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=f"HLK-DIO16 {client.host}",
            update_interval=timedelta(seconds=SCAN_INTERVAL_SECONDS),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            if not self.client.connected:
                await self.client.connect()
            inputs = await self.client.read_inputs()
            outputs = await self.client.read_outputs()
        except HlkDio16Error as err:
            raise UpdateFailed(str(err)) from err
        return {"inputs": inputs, "outputs": outputs}

    async def async_set_output(self, channel: int, state: bool) -> None:
        """Set an output and refresh coordinator data."""
        try:
            outputs = await self.client.set_output(channel, state)
            inputs = (self.data or {}).get("inputs") or await self.client.read_inputs()
        except HlkDio16Error as err:
            raise UpdateFailed(str(err)) from err
        self.async_set_updated_data({"inputs": inputs, "outputs": outputs})
