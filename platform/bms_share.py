"""Home Box limited-share consent (box gate only).

Toggle lives on the box. Does NOT grant any company access by itself.
Company visibility requires a separate BMS ShareGrant by the homeowner.

sensors: [{entity_id, system}] — system is client-chosen classification (never inferred).
sensor_entities: derived id list for older readers.
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


def _normalize_entries(raw: Any) -> list[dict[str, str]]:
    try:
        from sensor_feed import normalize_sensor_entries
    except ImportError:
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
                system = str(item.get("system") or item.get("domain") or "").strip().lower()
            else:
                continue
            if not eid.startswith("binary_sensor.") or eid in seen:
                continue
            seen.add(eid)
            out.append({"entity_id": eid, "system": system})
        return out
    return normalize_sensor_entries(raw)


def load_share() -> dict[str, Any]:
    path = share_path()
    empty = {
        "v": 2,
        "limited_share_enabled": False,
        "scope": list(DEFAULT_SCOPE),
        "sensors": [],
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
    raw = data.get("sensors")
    if raw is None:
        raw = data.get("sensor_entities")
    sensors = _normalize_entries(raw)
    return {
        "v": 2,
        "limited_share_enabled": bool(data.get("limited_share_enabled")),
        "scope": list(data.get("scope") or DEFAULT_SCOPE),
        "sensors": sensors,
        "sensor_entities": [s["entity_id"] for s in sensors],
        "updated_at": data.get("updated_at"),
        "note": data.get("note"),
    }


def limited_share_enabled() -> bool:
    return bool(load_share().get("limited_share_enabled"))


def set_limited_share(
    enabled: bool,
    sensors: list[Any] | None = None,
    sensor_entities: list[Any] | None = None,
) -> dict[str, Any]:
    current = load_share()
    if sensors is not None:
        entries = _normalize_entries(sensors)
    elif sensor_entities is not None:
        # Preserve classifications when only ids are sent.
        prev = {s["entity_id"]: s.get("system") or "" for s in current.get("sensors") or []}
        merged = []
        for item in sensor_entities:
            if isinstance(item, dict):
                merged.append(item)
            else:
                eid = str(item or "").strip().lower()
                merged.append({"entity_id": eid, "system": prev.get(eid, "")})
        entries = _normalize_entries(merged)
    else:
        entries = list(current.get("sensors") or [])
    body = {
        "v": 2,
        "limited_share_enabled": bool(enabled),
        "scope": list(DEFAULT_SCOPE),
        "sensors": entries,
        "sensor_entities": [s["entity_id"] for s in entries],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Box consent only. Client labels each sensor (domain or location). "
            "No company sees data until the homeowner grants them in BMS."
        ),
    }
    path = share_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return body
