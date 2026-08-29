"""Cache BMS subscription flags for Home Box local UIs (no secrets)."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
RUNTIME_PATH = Path(os.environ.get("BMS_RUNTIME_PATH", str(CONFIG / "bms_runtime.json")))


def runtime_path() -> Path:
    return RUNTIME_PATH


def save_runtime_from_snapshot(snap: dict[str, Any]) -> dict[str, Any]:
    """Persist enablement flags from ingest snapshot. Never store passwords."""
    machine = snap.get("machine") if isinstance(snap.get("machine"), dict) else {}
    household = snap.get("household") if isinstance(snap.get("household"), dict) else {}
    body = {
        "v": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "unique_id": snap.get("unique_id") or snap.get("appliance_uid"),
        "fail_closed": bool(snap.get("fail_closed")),
        "live_status": snap.get("live_status"),
        "allow_password_reset": bool(machine.get("allow_password_reset")),
        "shares": snap.get("shares") if isinstance(snap.get("shares"), list) else [],
        "machine": {
            "id": machine.get("id"),
            "name": machine.get("name"),
            "site_slug": machine.get("site_slug"),
            "ha_hostname": machine.get("ha_hostname"),
            "handover_state": machine.get("handover_state"),
            "allow_password_reset": bool(machine.get("allow_password_reset")),
            "limited_share_enabled": machine.get("limited_share_enabled"),
        },
        "household": {
            "slug": household.get("slug"),
            "name": household.get("name"),
            "ha_hostname": household.get("ha_hostname"),
        },
    }
    path = runtime_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return body


def load_runtime() -> dict[str, Any] | None:
    path = runtime_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return data if isinstance(data, dict) else None
