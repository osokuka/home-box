"""Sensory feed mapping for BMS ingest (read-only).

Deep module: callers pass HA states + share config and get
(devices, should_push) without knowing entity-id rules.
"""

from __future__ import annotations

import re
from typing import Any


def slug_key(name: str, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return text or fallback


def is_shareable_sensor_entity(entity_id: str) -> bool:
    """Only binary_sensor.* — never switches / relays / controls."""
    eid = (entity_id or "").strip().lower()
    return eid.startswith("binary_sensor.")


def normalize_sensor_entities(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        eid = str(item or "").strip().lower()
        if not is_shareable_sensor_entity(eid):
            continue
        if eid in seen:
            continue
        seen.add(eid)
        out.append(eid)
    return out


def map_climate(state: dict) -> dict[str, Any]:
    attrs = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
    ha_state = str(state.get("state") or "unknown")
    if ha_state in ("unavailable", "unknown", ""):
        health = "offline" if ha_state == "unavailable" else "unknown"
        mode = "unknown"
    else:
        health = "online"
        mode = ha_state
    telemetry: dict[str, Any] = {"hvac.mode": mode}
    temp = attrs.get("current_temperature")
    setpoint = attrs.get("temperature")
    if temp is not None:
        telemetry["hvac.temperature"] = temp
    if setpoint is not None:
        telemetry["hvac.setpoint_heat"] = setpoint
    action = attrs.get("hvac_action")
    if action:
        telemetry["hvac.action"] = action
    title = attrs.get("friendly_name") or "Heat pump"
    return {
        "id": slug_key(title, "heat-pump"),
        "class": "heat_pump",
        "system": "hvac",
        "display_name": title,
        "health": health,
        "telemetry": telemetry,
    }


def map_binary_sensor(state: dict) -> dict[str, Any] | None:
    eid = str(state.get("entity_id") or "")
    if not is_shareable_sensor_entity(eid):
        return None
    attrs = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
    ha_state = str(state.get("state") or "unknown").lower()
    if ha_state in ("unavailable", "unknown", ""):
        health = "offline" if ha_state == "unavailable" else "unknown"
        active = None
    else:
        health = "online"
        active = ha_state in ("on", "true", "1", "open", "detected")
    title = attrs.get("friendly_name") or eid
    device_class = str(attrs.get("device_class") or "sensor")
    return {
        "id": slug_key(title, eid.replace(".", "-")),
        "class": "binary_input",
        "system": "security",
        "display_name": title,
        "health": health,
        "telemetry": {
            "sensor.entity_id": eid,
            "sensor.state": active,
            "sensor.raw": ha_state,
            "sensor.device_class": device_class,
        },
    }


def collect_devices(
    states: list[dict] | None,
    *,
    climate_entity: str,
    sensor_entities: list[str],
    include_climate: bool = True,
) -> list[dict[str, Any]]:
    """Build BMS device list from HA states (sensors allowlist + optional climate)."""
    devices: list[dict[str, Any]] = []
    by_id: dict[str, dict] = {}
    if isinstance(states, list):
        for st in states:
            if isinstance(st, dict) and st.get("entity_id"):
                by_id[str(st["entity_id"]).lower()] = st

    allowed = normalize_sensor_entities(sensor_entities)
    for eid in allowed:
        st = by_id.get(eid)
        if not st:
            devices.append(
                {
                    "id": slug_key(eid, eid.replace(".", "-")),
                    "class": "binary_input",
                    "system": "security",
                    "display_name": eid,
                    "health": "unknown",
                    "telemetry": {
                        "sensor.entity_id": eid,
                        "sensor.state": None,
                        "sensor.raw": "missing",
                    },
                }
            )
            continue
        mapped = map_binary_sensor(st)
        if mapped:
            devices.append(mapped)

    if include_climate:
        climate = by_id.get((climate_entity or "").strip().lower())
        if climate:
            devices.append(map_climate(climate))
        else:
            # Prefer any climate.* if configured entity missing
            for eid, st in by_id.items():
                if eid.startswith("climate."):
                    devices.append(map_climate(st))
                    break

    return devices


def feed_is_positive(devices: list[dict[str, Any]]) -> bool:
    """Idle/empty feeds must not be posted. Positive = active sensor or active HVAC."""
    if not devices:
        return False
    for device in devices:
        cls = str(device.get("class") or "")
        tel = device.get("telemetry") if isinstance(device.get("telemetry"), dict) else {}
        if cls == "binary_input":
            if tel.get("sensor.state") is True:
                return True
            continue
        if cls == "heat_pump":
            mode = str(tel.get("hvac.mode") or "").lower()
            health = str(device.get("health") or "")
            if health != "online":
                continue
            if mode in ("off", "unknown", ""):
                continue
            return True
    return False


def share_signature(share: dict[str, Any]) -> str:
    """Stable signature of box share consent + allowlist (for change detection)."""
    enabled = "1" if share.get("limited_share_enabled") else "0"
    updated = str(share.get("updated_at") or "")
    sensors = ",".join(normalize_sensor_entities(share.get("sensor_entities")))
    return f"{enabled}|{updated}|{sensors}"


def should_post_feed(
    *,
    share_on: bool,
    share_changed: bool,
    devices: list[dict[str, Any]],
    sensor_entities: list[str],
) -> tuple[bool, str]:
    """Decide whether to POST /ingest/status/.

    Returns (should_post, reason).
    Share allowlist changes always push (including off / empty list).
    Otherwise only positive feeds are posted while share is on.
    """
    if share_changed:
        return True, "share_changed"
    if not share_on:
        return False, "share_off"
    if feed_is_positive(devices):
        return True, "positive"
    if sensor_entities and not devices:
        return False, "idle_no_states"
    return False, "idle"


def collect_support_activity(states: list[dict] | None = None) -> list[dict[str, Any]]:
    """Limited troubleshooting signals — not full logs."""
    events: list[dict[str, Any]] = []
    if not isinstance(states, list):
        return events
    for st in states:
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id") or "")
        attrs = st.get("attributes") if isinstance(st.get("attributes"), dict) else {}
        state = str(st.get("state") or "")
        name = str(attrs.get("friendly_name") or eid)
        if "fault" in eid or "fault" in name.lower():
            events.append(
                {
                    "type": "fault_signal",
                    "entity_id": eid,
                    "state": state,
                    "name": name,
                }
            )
        elif eid.startswith("climate.") and state in ("unavailable", "unknown"):
            events.append(
                {
                    "type": "device_unreachable",
                    "entity_id": eid,
                    "state": state,
                    "name": name,
                }
            )
        elif is_shareable_sensor_entity(eid) and state in ("unavailable", "unknown"):
            events.append(
                {
                    "type": "device_unreachable",
                    "entity_id": eid,
                    "state": state,
                    "name": name,
                }
            )
    return events[:50]
