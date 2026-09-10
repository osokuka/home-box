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
    should_idle_snapshot,
    should_post_feed,
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
        sensors=[{"entity_id": "binary_sensor.door", "system": "security"}],
    )
    assert len(devices) == 2
    assert feed_is_positive(devices) is False
    assert devices[0]["system"] == "security"


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
        sensors=[{"entity_id": "binary_sensor.door", "system": "hvac"}],
        include_climate=False,
    )
    assert feed_is_positive(devices) is True
    assert devices[0]["system"] == "hvac"
    assert devices[0]["display_name"] == "Door"


def test_client_classification_not_assumed() -> None:
    states = [
        {
            "entity_id": "binary_sensor.door",
            "state": "off",
            "attributes": {"friendly_name": "Door"},
        }
    ]
    devices = collect_devices(
        states,
        climate_entity="climate.heat_pump",
        sensors=[{"entity_id": "binary_sensor.door", "system": ""}],
        include_climate=False,
    )
    assert devices[0]["system"] == ""


def test_location_classification_pushed() -> None:
    states = [
        {
            "entity_id": "binary_sensor.door",
            "state": "off",
            "attributes": {"friendly_name": "Door"},
        }
    ]
    devices = collect_devices(
        states,
        climate_entity="climate.heat_pump",
        sensors=[{"entity_id": "binary_sensor.door", "system": "Front Door"}],
        include_climate=False,
    )
    assert devices[0]["system"] == "front-door"
    assert devices[0]["telemetry"]["sensor.classification"] == "front-door"


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
        sensors=[],
    )
    assert feed_is_positive(devices) is True


def test_share_change_always_posts() -> None:
    ok, reason = should_post_feed(
        share_on=True,
        share_changed=True,
        devices=[],
        sensor_entities=["binary_sensor.door"],
    )
    assert ok and reason == "share_changed"
    ok2, reason2 = should_post_feed(
        share_on=False,
        share_changed=True,
        devices=[],
        sensor_entities=[],
    )
    assert ok2 and reason2 == "share_changed"


def test_idle_skipped_without_change() -> None:
    devices = [
        {
            "class": "binary_input",
            "health": "online",
            "telemetry": {"sensor.state": False},
        }
    ]
    ok, reason = should_post_feed(
        share_on=True,
        share_changed=False,
        devices=devices,
        sensor_entities=["binary_sensor.door"],
    )
    assert not ok and reason == "idle"
    assert should_idle_snapshot(
        share_on=True,
        feed_reason="idle",
        seconds_since_last_post=60.0,
        interval_seconds=60.0,
    )
    assert not should_idle_snapshot(
        share_on=True,
        feed_reason="idle",
        seconds_since_last_post=10.0,
        interval_seconds=60.0,
    )
    assert not should_idle_snapshot(
        share_on=False,
        feed_reason="idle",
        seconds_since_last_post=120.0,
        interval_seconds=60.0,
    )


def main() -> None:
    test_rejects_switches()
    test_idle_when_sensors_off()
    test_positive_when_sensor_on()
    test_client_classification_not_assumed()
    test_location_classification_pushed()
    test_positive_when_hvac_active()
    test_share_change_always_posts()
    test_idle_skipped_without_change()
    print("sensor_feed checks: OK")


if __name__ == "__main__":
    main()
