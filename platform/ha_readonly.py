"""Read-only Home Assistant helpers for Home Box MCP (GET only — never /api/services)."""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

HA_URL = os.environ.get("BMS_HA_URL", "http://homeassistant:8123").rstrip("/")
HA_TOKEN = os.environ.get("BMS_HA_TOKEN", "").strip()
CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
CLIMATE_ENTITY = os.environ.get("BMS_CLIMATE_ENTITY", "climate.heat_pump")

# Domains agents may inspect (status only).
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


def box_status() -> dict[str, Any]:
    ha_ok = False
    version = None
    detail = "ok"
    try:
        cfg = ha_get("/api/config")
        ha_ok = True
        if isinstance(cfg, dict):
            version = cfg.get("version")
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
        "detail": detail,
        "commands_allowed": False,
        "note": "MCP tools are read-only. No device control via AI agents.",
    }


def list_devices(domain: str | None = None) -> list[dict[str, Any]]:
    states = ha_get("/api/states")
    if not isinstance(states, list):
        return []
    out: list[dict[str, Any]] = []
    want = (domain or "").strip().lower() or None
    for st in states:
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
        out.append(
            {
                "entity_id": eid,
                "state": st.get("state"),
                "friendly_name": attrs.get("friendly_name") or eid,
                "domain": dom,
            }
        )
    out.sort(key=lambda x: x["entity_id"])
    return out


def get_climate(entity_id: str | None = None) -> list[dict[str, Any]]:
    target = (entity_id or CLIMATE_ENTITY or "").strip()
    states = ha_get("/api/states")
    if not isinstance(states, list):
        return []
    rows: list[dict[str, Any]] = []
    for st in states:
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
            }
        )
    return rows


def get_areas() -> list[dict[str, Any]]:
    # Prefer HA API if available in this version; else registry file.
    try:
        areas = ha_get("/api/config/area_registry")
        if isinstance(areas, list):
            return [
                {
                    "area_id": a.get("area_id") or a.get("id"),
                    "name": a.get("name"),
                    "aliases": a.get("aliases") or [],
                }
                for a in areas
                if isinstance(a, dict)
            ]
    except Exception:
        pass
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
        }
        for a in areas
        if isinstance(a, dict)
    ]
