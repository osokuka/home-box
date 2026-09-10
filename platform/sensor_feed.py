"""Sensory feed mapping for BMS ingest (read-only).

Deep module: callers pass HA states + share config and get
(devices, should_push) without knowing entity-id rules.

Sensor domain/system is client-chosen — never inferred (no hardcoded security/hvac for DI).
"""

from __future__ import annotations

import re
from typing import Any


def slug_key(name: str, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return text or fallback


def classify_system(raw: Any) -> str:
    """Normalize client classification (domain or location) — empty if unset.

    Clients choose freely (e.g. ``hvac``, ``security``, ``kitchen``, ``front-door``).
    Home Box never invents a value; we only slug for stable transport.
    """
    return slug_key(str(raw or "").strip(), "")


def is_shareable_sensor_entity(entity_id: str) -> bool:
    """Only binary_sensor.* — never switches / relays / controls."""
    eid = (entity_id or "").strip().lower()
    return eid.startswith("binary_sensor.")


def normalize_sensor_entries(raw: Any) -> list[dict[str, str]]:
    """Accept legacy string ids or {entity_id, system} objects."""
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    seen: set[str] = set()
    for item in raw:
        if isinstance(item, str):
            eid = item.strip().lower()
            system = ""
        elif isinstance(item, dict):
            eid = str(item.get("entity_id") or "").strip().lower()
            system = classify_system(item.get("system") or item.get("domain") or "")
        else:
            continue
        if not is_shareable_sensor_entity(eid) or eid in seen:
            continue
        seen.add(eid)
        out.append({"entity_id": eid, "system": system})
    return out


def normalize_sensor_entities(raw: Any) -> list[str]:
    return [row["entity_id"] for row in normalize_sensor_entries(raw)]


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
    # Climate entities are HVAC by nature of the HA domain (climate.*), not a guess.
    return {
        "id": slug_key(title, "heat-pump"),
        "class": "heat_pump",
        "system": "hvac",
        "display_name": title,
        "health": health,
        "telemetry": telemetry,
    }


def map_binary_sensor(
    state: dict, *, system: str
) -> dict[str, Any] | None:
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
    system_slug = classify_system(system)
    return {
        "id": slug_key(title, eid.replace(".", "-")),
        "class": "binary_input",
        "system": system_slug,
        "display_name": title,
        "health": health,
        "telemetry": {
            "sensor.entity_id": eid,
            "sensor.state": active,
            "sensor.raw": ha_state,
            "sensor.device_class": device_class,
            "sensor.system": system_slug,
            "sensor.classification": system_slug,
        },
    }


def collect_devices(
    states: list[dict] | None,
    *,
    climate_entity: str,
    sensors: list[dict[str, str]] | None = None,
    sensor_entities: list[str] | None = None,
    include_climate: bool = True,
) -> list[dict[str, Any]]:
    """Build BMS device list from HA states + client sensor classifications."""
    devices: list[dict[str, Any]] = []
    by_id: dict[str, dict] = {}
    if isinstance(states, list):
        for st in states:
            if isinstance(st, dict) and st.get("entity_id"):
                by_id[str(st["entity_id"]).lower()] = st

    entries = normalize_sensor_entries(sensors if sensors is not None else sensor_entities)
    for entry in entries:
        eid = entry["entity_id"]
        system = entry.get("system") or ""
        st = by_id.get(eid)
        system_slug = classify_system(system)
        if not st:
            devices.append(
                {
                    "id": slug_key(eid, eid.replace(".", "-")),
                    "class": "binary_input",
                    "system": system_slug,
                    "display_name": eid,
                    "health": "unknown",
                    "telemetry": {
                        "sensor.entity_id": eid,
                        "sensor.state": None,
                        "sensor.raw": "missing",
                        "sensor.system": system_slug,
                        "sensor.classification": system_slug,
                    },
                }
            )
            continue
        mapped = map_binary_sensor(st, system=system_slug)
        if mapped:
            devices.append(mapped)

    if include_climate:
        climate = by_id.get((climate_entity or "").strip().lower())
        if climate:
            devices.append(map_climate(climate))
        else:
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
    """Stable signature of box share consent + allowlist + classifications."""
    enabled = "1" if share.get("limited_share_enabled") else "0"
    updated = str(share.get("updated_at") or "")
    entries = normalize_sensor_entries(
        share.get("sensors")
        if share.get("sensors") is not None
        else share.get("sensor_entities")
    )
    sensors = ",".join(f"{e['entity_id']}:{e.get('system') or ''}" for e in entries)
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
    Positive feeds post immediately while share is on.
    Idle feeds are left to the agent idle-snapshot timer (see should_idle_snapshot).
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


def should_idle_snapshot(
    *,
    share_on: bool,
    feed_reason: str,
    seconds_since_last_post: float,
    interval_seconds: float = 60.0,
) -> bool:
    """True when share is on, feed is idle, and the idle snapshot interval elapsed."""
    if not share_on:
        return False
    if feed_reason not in {"idle", "idle_no_states"}:
        return False
    if interval_seconds <= 0:
        return False
    return seconds_since_last_post >= interval_seconds


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
