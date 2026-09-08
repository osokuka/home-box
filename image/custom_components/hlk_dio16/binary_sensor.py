"""Digital input binary sensors for HLK-DIO16."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CHANNEL_COUNT, CONF_HOST, CONF_PORT, DEFAULT_PORT, DOMAIN
from .coordinator import HlkDio16Coordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up HLK-DIO16 binary sensors from a config entry."""
    coordinator: HlkDio16Coordinator = hass.data[DOMAIN][entry.entry_id]["coordinator"]
    async_add_entities(
        HlkDio16InputSensor(coordinator, entry, channel)
        for channel in range(1, CHANNEL_COUNT + 1)
    )


class HlkDio16InputSensor(CoordinatorEntity[HlkDio16Coordinator], BinarySensorEntity):
    """One digital input channel."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: HlkDio16Coordinator,
        entry: ConfigEntry,
        channel: int,
    ) -> None:
        super().__init__(coordinator)
        self._channel = channel
        host = entry.data[CONF_HOST]
        port = entry.data.get(CONF_PORT, DEFAULT_PORT)
        self._attr_unique_id = f"{entry.entry_id}_di_{channel:02d}"
        self._attr_name = f"DI{channel:02d}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, f"{host}:{port}")},
            name=entry.title,
            manufacturer="Hi-Link",
            model="HLK-DIO16",
        )

    @property
    def is_on(self) -> bool | None:
        """Return True when the input is active/high."""
        if not self.coordinator.data:
            return None
        return bool(self.coordinator.data["inputs"].get(self._channel))
