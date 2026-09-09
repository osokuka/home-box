"""Unit checks for sensory feed mapping (no HA / BMS required)."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLATFORM = ROOT / "platform"
sys.path.insert(0, str(PLATFORM))

from sensor_feed import (  # noqa: E402
    collect_devices,
    feed_is_positive,
    is_shareable_sensor_entity,
    normalize_sensor_entities,
)


def test_rejects_switches() -> None:
    assert is_shareable_sensor_entity("binary_sensor.hlk_di01")
    assert not is_shareable_sensor_entity("switch.hlk_do01")
    assert normalize_sensor_entities(
        ["binary_sensor.a", "switch.b", "binary_sensor.a", "climate.x"]
    ) == ["binary_sensor.a"]


def test_idle_when_sensors_off() -> None:
    states = [
        {
            "entity_id": "binary_sensor.door",
            "state": "off",
            "attributes": {"friendly_name": "Door"},
        },
        {
            "entity_id": "climate.heat_pump",
            "state": "off",
            "attributes": {"friendly_name": "Heat pump"},
        },
    ]
    devices = collect_devices(
        states,
        climate_entity="climate.heat_pump",
        sensor_entities=["binary_sensor.door"],
    )
    assert len(devices) == 2
    assert feed_is_positive(devices) is False


def test_positive_when_sensor_on() -> None:
    states = [
        {
            "entity_id": "binary_sensor.door",
            "state": "on",
            "attributes": {"friendly_name": "Door"},
        }
    ]
    devices = collect_devices(
        states,
        climate_entity="climate.heat_pump",
        sensor_entities=["binary_sensor.door"],
        include_climate=False,
    )
    assert feed_is_positive(devices) is True
    assert devices[0]["system"] == "security"
    assert "switch" not in devices[0]["telemetry"].get("sensor.entity_id", "")


def test_positive_when_hvac_active() -> None:
    states = [
        {
            "entity_id": "climate.heat_pump",
            "state": "heat",
            "attributes": {
                "friendly_name": "Heat pump",
                "current_temperature": 21,
                "hvac_action": "heating",
            },
        }
    ]
    devices = collect_devices(
        states,
        climate_entity="climate.heat_pump",
        sensor_entities=[],
    )
    assert feed_is_positive(devices) is True


def main() -> None:
    test_rejects_switches()
    test_idle_when_sensors_off()
    test_positive_when_sensor_on()
    test_positive_when_hvac_active()
    print("sensor_feed checks: OK")


if __name__ == "__main__":
    main()
