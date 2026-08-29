"""Home Box limited-share consent (box gate only).

Toggle lives on the box. Does NOT grant any company access by itself.
Company visibility requires a separate BMS ShareGrant by the homeowner.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
SHARE_PATH = Path(os.environ.get("BMS_SHARE_PATH", str(CONFIG / "bms_share.json")))


def share_path() -> Path:
    return SHARE_PATH


def load_share() -> dict[str, Any]:
    path = share_path()
    if not path.is_file():
        return {
            "v": 1,
            "limited_share_enabled": False,
            "scope": ["status", "support_activity"],
            "updated_at": None,
        }
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {
            "v": 1,
            "limited_share_enabled": False,
            "scope": ["status", "support_activity"],
            "updated_at": None,
        }
    if not isinstance(data, dict):
        return {
            "v": 1,
            "limited_share_enabled": False,
            "scope": ["status", "support_activity"],
            "updated_at": None,
        }
    return {
        "v": int(data.get("v") or 1),
        "limited_share_enabled": bool(data.get("limited_share_enabled")),
        "scope": list(data.get("scope") or ["status", "support_activity"]),
        "updated_at": data.get("updated_at"),
    }


def limited_share_enabled() -> bool:
    return bool(load_share().get("limited_share_enabled"))


def set_limited_share(enabled: bool) -> dict[str, Any]:
    body = {
        "v": 1,
        "limited_share_enabled": bool(enabled),
        "scope": ["status", "support_activity"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "Box consent only. No company sees data until the homeowner "
            "grants a limited share to that company in BMS."
        ),
    }
    path = share_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return body
