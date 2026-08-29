"""Read-only Home Assistant helpers for Home Box MCP (GET only — never call services)."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HA_URL = os.environ.get("BMS_HA_URL", "http://homeassistant:8123").rstrip("/")
HA_TOKEN = os.environ.get("BMS_HA_TOKEN", "").strip()
CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
CLIMATE_ENTITY = os.environ.get("BMS_CLIMATE_ENTITY", "climate.heat_pump")

ALLOWED_DOMAINS = frozenset(
    {
        "climate",
        "sensor",
        "binary_sensor",
        "switch",
        "select",
        "number",
        "cover",
        "light",
        "fan",
        "lock",
        "water_heater",
        "humidifier",
        "weather",
        "person",
        "zone",
        "sun",
        "media_player",
        "vacuum",
        "alarm_control_panel",
        "valve",
        "input_boolean",
        "input_number",
        "input_select",
        "input_text",
    }
)

ENERGY_HINTS = re.compile(
    r"(energy|power|watt|kwh|consumption|grid|solar|battery|amper|volt)",
    re.I,
)

# Attribute keys that look like secrets — never return to agents.
REDACT_ATTR_KEYS = frozenset(
    {
        "access_token",
        "token",
        "local_key",
        "password",
        "secret",
        "api_key",
        "private_key",
        "refresh_token",
    }
)


def ha_get(path: str) -> Any:
    if not HA_TOKEN:
        raise RuntimeError(
            "BMS_HA_TOKEN is not set — create a long-lived token in Home Box "
            "(owner profile) and set it on the home-box-mcp service."
        )
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        headers={"Authorization": f"Bearer {HA_TOKEN}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")[:300]
        raise RuntimeError(f"HA GET {path} failed HTTP {err.code}: {body}") from err
    except Exception as err:
        raise RuntimeError(f"HA GET {path} failed: {err}") from err


def read_storage(name: str) -> Any | None:
    path = CONFIG / ".storage" / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_attrs(attrs: dict) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in attrs.items():
        lk = str(k).lower()
        if lk in REDACT_ATTR_KEYS or any(x in lk for x in ("password", "secret", "token", "local_key")):
            out[k] = "[redacted]"
        else:
            out[k] = v
    return out


def _summarize_state(st: dict, full: bool = False) -> dict[str, Any]:
    eid = str(st.get("entity_id") or "")
    dom = eid.split(".", 1)[0] if "." in eid else ""
    attrs = st.get("attributes") if isinstance(st.get("attributes"), dict) else {}
    row: dict[str, Any] = {
        "entity_id": eid,
        "domain": dom,
        "state": st.get("state"),
        "friendly_name": attrs.get("friendly_name") or eid,
        "unit_of_measurement": attrs.get("unit_of_measurement"),
        "device_class": attrs.get("device_class"),
        "last_changed": st.get("last_changed"),
        "last_updated": st.get("last_updated"),
    }
    if full:
        row["attributes"] = _safe_attrs(attrs)
    return {k: v for k, v in row.items() if v is not None}


def _all_states() -> list[dict]:
    states = ha_get("/api/states")
    return states if isinstance(states, list) else []


def box_status() -> dict[str, Any]:
    ha_ok = False
    version = None
    detail = "ok"
    location = None
    try:
        cfg = ha_get("/api/config")
        ha_ok = True
        if isinstance(cfg, dict):
            version = cfg.get("version")
            location = {
                "location_name": cfg.get("location_name"),
                "time_zone": cfg.get("time_zone"),
                "unit_system": cfg.get("unit_system"),
                "currency": cfg.get("currency"),
                "country": cfg.get("country"),
                "language": cfg.get("language"),
            }
    except Exception as err:
        detail = str(err)
        ha_ok = False
    ha_ver_file = CONFIG / ".HA_VERSION"
    return {
        "product": "Home Box",
        "ha_reachable": ha_ok,
        "ha_version": version
        or (ha_ver_file.read_text(encoding="utf-8").strip() if ha_ver_file.is_file() else None),
        "config_on_disk": (CONFIG / ".storage" / "core.config").is_file(),
        "location": location,
        "detail": detail,
        "commands_allowed": False,
        "note": "MCP tools are read-only. No device control via AI agents.",
    }


def get_ha_config() -> dict[str, Any]:
    cfg = ha_get("/api/config")
    if not isinstance(cfg, dict):
        return {"error": "unexpected config payload"}
    # Drop internals that are not useful / sensitive for agents.
    keep = (
        "version",
        "location_name",
        "time_zone",
        "unit_system",
        "currency",
        "country",
        "language",
        "state",
        "external_url",
        "internal_url",
        "allowlist_external_dirs",
        "components",
    )
    out = {k: cfg.get(k) for k in keep if k in cfg}
    comps = out.get("components")
    if isinstance(comps, list):
        # Cap size — agents only need to know notable integrations exist.
        interesting = sorted(
            c
            for c in comps
            if isinstance(c, str)
            and any(
                x in c
                for x in (
                    "tuya",
                    "climate",
                    "mqtt",
                    "zha",
                    "matter",
                    "energy",
                    "mobile_app",
                    "person",
                )
            )
        )
        out["components_sample"] = interesting[:80]
        out["components_count"] = len(comps)
        del out["components"]
    out["commands_allowed"] = False
    return out


def list_ha_services(domain: str | None = None) -> dict[str, Any]:
    """Catalog only — does not execute any service."""
    services = ha_get("/api/services")
    if not isinstance(services, list):
        return {"count": 0, "domains": [], "note": "unexpected services payload"}
    want = (domain or "").strip().lower() or None
    domains = []
    for block in services:
        if not isinstance(block, dict):
            continue
        dom = str(block.get("domain") or "")
        if want and dom != want:
            continue
        svc_map = block.get("services") if isinstance(block.get("services"), dict) else {}
        domains.append(
            {
                "domain": dom,
                "services": sorted(svc_map.keys()),
                "service_count": len(svc_map),
            }
        )
    domains.sort(key=lambda x: x["domain"])
    return {
        "count": len(domains),
        "domains": domains,
        "commands_allowed": False,
        "note": "Catalog only. Home Box MCP cannot call these services.",
    }


def list_devices(domain: str | None = None) -> list[dict[str, Any]]:
    want = (domain or "").strip().lower() or None
    out: list[dict[str, Any]] = []
    for st in _all_states():
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id") or "")
        if "." not in eid:
            continue
        dom = eid.split(".", 1)[0]
        if dom not in ALLOWED_DOMAINS:
            continue
        if want and dom != want:
            continue
        out.append(_summarize_state(st, full=False))
    out.sort(key=lambda x: x["entity_id"])
    return out


def get_entity(entity_id: str) -> dict[str, Any]:
    eid = (entity_id or "").strip()
    if not eid or "." not in eid:
        raise RuntimeError("entity_id required, e.g. climate.heat_pump")
    dom = eid.split(".", 1)[0]
    if dom not in ALLOWED_DOMAINS:
        raise RuntimeError(f"domain '{dom}' is not exposed to MCP agents")
    st = ha_get(f"/api/states/{eid}")
    if not isinstance(st, dict):
        raise RuntimeError("entity not found or unexpected payload")
    return _summarize_state(st, full=True)


def get_entities(entity_ids: str = "", domain: str = "") -> list[dict[str, Any]]:
    ids = [x.strip() for x in (entity_ids or "").split(",") if x.strip()]
    if ids:
        rows = []
        for eid in ids:
            try:
                rows.append(get_entity(eid))
            except Exception as err:
                rows.append({"entity_id": eid, "error": str(err)})
        return rows
    return list_devices(domain or None)


def search_entities(query: str, domain: str = "") -> list[dict[str, Any]]:
    q = (query or "").strip().lower()
    if not q:
        raise RuntimeError("query is required")
    want = (domain or "").strip().lower() or None
    hits = []
    for st in _all_states():
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id") or "")
        if "." not in eid:
            continue
        dom = eid.split(".", 1)[0]
        if dom not in ALLOWED_DOMAINS:
            continue
        if want and dom != want:
            continue
        attrs = st.get("attributes") if isinstance(st.get("attributes"), dict) else {}
        name = str(attrs.get("friendly_name") or "")
        if q in eid.lower() or q in name.lower():
            hits.append(_summarize_state(st, full=False))
    hits.sort(key=lambda x: x["entity_id"])
    return hits[:200]


def _by_domain(domain: str) -> list[dict[str, Any]]:
    return list_devices(domain)


def get_climate(entity_id: str | None = None) -> list[dict[str, Any]]:
    target = (entity_id or CLIMATE_ENTITY or "").strip()
    rows: list[dict[str, Any]] = []
    for st in _all_states():
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id") or "")
        if not eid.startswith("climate."):
            continue
        if target and eid != target and target != "*":
            continue
        attrs = st.get("attributes") if isinstance(st.get("attributes"), dict) else {}
        rows.append(
            {
                "entity_id": eid,
                "state": st.get("state"),
                "friendly_name": attrs.get("friendly_name"),
                "current_temperature": attrs.get("current_temperature"),
                "temperature": attrs.get("temperature"),
                "hvac_action": attrs.get("hvac_action"),
                "hvac_modes": attrs.get("hvac_modes"),
                "preset_mode": attrs.get("preset_mode"),
            }
        )
    return rows


def get_energy_snapshot() -> dict[str, Any]:
    sensors = []
    for st in _all_states():
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id") or "")
        if not eid.startswith("sensor."):
            continue
        attrs = st.get("attributes") if isinstance(st.get("attributes"), dict) else {}
        name = str(attrs.get("friendly_name") or eid)
        dc = str(attrs.get("device_class") or "")
        unit = str(attrs.get("unit_of_measurement") or "")
        blob = f"{eid} {name} {dc} {unit}"
        if ENERGY_HINTS.search(blob) or dc in (
            "energy",
            "power",
            "energy_storage",
            "battery",
            "current",
            "voltage",
            "gas",
            "water",
        ):
            sensors.append(_summarize_state(st, full=False))
    sensors.sort(key=lambda x: x["entity_id"])
    return {
        "count": len(sensors),
        "sensors": sensors[:150],
        "note": "Heuristic match on energy/power-related sensors. Read-only.",
    }


def get_areas() -> list[dict[str, Any]]:
    blob = read_storage("core.area_registry")
    data = blob.get("data") if isinstance(blob, dict) else None
    areas = data.get("areas") if isinstance(data, dict) else data
    if not isinstance(areas, list):
        return []
    return [
        {
            "area_id": a.get("id") or a.get("area_id"),
            "name": a.get("name"),
            "aliases": a.get("aliases") or [],
            "icon": a.get("icon"),
        }
        for a in areas
        if isinstance(a, dict)
    ]


def get_devices_registry() -> dict[str, Any]:
    blob = read_storage("core.device_registry")
    data = blob.get("data") if isinstance(blob, dict) else None
    devices = data.get("devices") if isinstance(data, dict) else None
    if not isinstance(devices, list):
        return {"count": 0, "devices": []}
    rows = []
    for d in devices:
        if not isinstance(d, dict):
            continue
        if d.get("disabled_by"):
            continue
        rows.append(
            {
                "id": d.get("id"),
                "name": d.get("name_by_user") or d.get("name"),
                "manufacturer": d.get("manufacturer"),
                "model": d.get("model"),
                "area_id": d.get("area_id"),
                "identifiers": d.get("identifiers"),
                "entry_type": d.get("entry_type"),
            }
        )
    rows.sort(key=lambda x: str(x.get("name") or ""))
    return {"count": len(rows), "devices": rows[:300]}


def get_people() -> list[dict[str, Any]]:
    rows = []
    for st in _all_states():
        if not isinstance(st, dict):
            continue
        eid = str(st.get("entity_id") or "")
        if not eid.startswith("person."):
            continue
        attrs = st.get("attributes") if isinstance(st.get("attributes"), dict) else {}
        rows.append(
            {
                "entity_id": eid,
                "state": st.get("state"),
                "friendly_name": attrs.get("friendly_name"),
                "source": attrs.get("source"),
                # Do not expose user_id linkage details beyond presence.
            }
        )
    return rows


def list_config_entries() -> dict[str, Any]:
    blob = read_storage("core.config_entries")
    data = blob.get("data") if isinstance(blob, dict) else None
    entries = data.get("entries") if isinstance(data, dict) else None
    if not isinstance(entries, list):
        return {"count": 0, "entries": []}
    rows = []
    for e in entries:
        if not isinstance(e, dict):
            continue
        rows.append(
            {
                "domain": e.get("domain"),
                "title": e.get("title"),
                "source": e.get("source"),
                "disabled_by": e.get("disabled_by"),
                "unique_id": e.get("unique_id"),
            }
        )
    rows.sort(key=lambda x: (str(x.get("domain")), str(x.get("title"))))
    return {
        "count": len(rows),
        "entries": rows,
        "note": "No secrets or config entry data payloads — titles/domains only.",
    }
