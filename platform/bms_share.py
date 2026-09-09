"""Home Box limited-share consent (box gate only).

Toggle lives on the box. Does NOT grant any company access by itself.
Company visibility requires a separate BMS ShareGrant by the homeowner.

sensor_entities: allowlisted binary_sensor.* entity ids (never switches).
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
SHARE_PATH = Path(os.environ.get("BMS_SHARE_PATH", str(CONFIG / "bms_share.json")))

DEFAULT_SCOPE = ["status", "support_activity", "sensors"]


def share_path() -> Path:
    return SHARE_PATH


def _normalize_sensors(raw: Any) -> list[str]:
    try:
        from sensor_feed import normalize_sensor_entities
    except ImportError:
        # HA admin process may not have platform/ on sys.path
        if not isinstance(raw, list):
            return []
        out: list[str] = []
        seen: set[str] = set()
        for item in raw:
            eid = str(item or "").strip().lower()
            if not eid.startswith("binary_sensor."):
                continue
            if eid in seen:
                continue
            seen.add(eid)
            out.append(eid)
        return out
    return normalize_sensor_entities(raw)


def load_share() -> dict[str, Any]:
    path = share_path()
    empty = {
        "v": 1,
        "limited_share_enabled": False,
        "scope": list(DEFAULT_SCOPE),
        "sensor_entities": [],
        "updated_at": None,
    }
    if not path.is_file():
        return empty
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty
    if not isinstance(data, dict):
        return empty
    return {
        "v": int(data.get("v") or 1),
        "limited_share_enabled": bool(data.get("limited_share_enabled")),
        "scope": list(data.get("scope") or DEFAULT_SCOPE),
        "sensor_entities": _normalize_sensors(data.get("sensor_entities")),
        "updated_at": data.get("updated_at"),
        "note": data.get("note"),
    }


def limited_share_enabled() -> bool:
    return bool(load_share().get("limited_share_enabled"))


def set_limited_share(
    enabled: bool,
    sensor_entities: list[str] | None = None,
) -> dict[str, Any]:
    current = load_share()
    sensors = (
        _normalize_sensors(sensor_entities)
        if sensor_entities is not None
        else list(current.get("sensor_entities") or [])
    )
    body = {
        "v": 1,
        "limited_share_enabled": bool(enabled),
        "scope": list(DEFAULT_SCOPE),
        "sensor_entities": sensors,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Box consent only. Selects which sensory entities may leave toward BMS. "
            "No company sees data until the homeowner grants them in BMS."
        ),
    }
    path = share_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return body
