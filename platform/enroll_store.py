"""Persist BMS enroll payload on the house box (QR / paste from operator).

File: /config/bms_enroll.json (not committed). Matches operator QR:
  {"v":1,"unique_id":"...","enroll_token":"...","ha_hostname":"..."}
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
ENROLL_PATH = Path(os.environ.get("BMS_ENROLL_PATH", str(CONFIG / "bms_enroll.json")))


def enroll_path() -> Path:
    return ENROLL_PATH


def load_enroll() -> dict | None:
    path = enroll_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    token = str(data.get("enroll_token") or "").strip()
    uid = str(data.get("unique_id") or data.get("appliance_uid") or "").strip()
    if not token or not uid:
        return None
    return data


def save_enroll(payload: dict) -> dict:
    """Normalize and write enroll. Raises ValueError on bad input."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    # Accept raw QR JSON or nested under qr_payload string.
    if "enroll_token" not in payload and isinstance(payload.get("qr_payload"), str):
        try:
            nested = json.loads(payload["qr_payload"])
        except Exception as err:
            raise ValueError("qr_payload is not valid JSON") from err
        if isinstance(nested, dict):
            payload = {**nested, **{k: v for k, v in payload.items() if k != "qr_payload"}}

    token = str(payload.get("enroll_token") or "").strip()
    uid = str(payload.get("unique_id") or payload.get("appliance_uid") or "").strip()
    hostname = str(payload.get("ha_hostname") or "").strip()
    platform_url = str(payload.get("platform_url") or "").strip().rstrip("/")

    if not token:
        raise ValueError("enroll_token is required")
    if not uid:
        raise ValueError("unique_id is required")

    body = {
        "v": int(payload.get("v") or 1),
        "unique_id": uid,
        "appliance_uid": uid,
        "enroll_token": token,
        "ha_hostname": hostname,
        "enrolled_at": datetime.now(timezone.utc).isoformat(),
    }
    if platform_url:
        body["platform_url"] = platform_url

    path = enroll_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    return body


def clear_enroll() -> bool:
    path = enroll_path()
    if path.is_file():
        path.unlink()
        return True
    return False


def public_status() -> dict:
    data = load_enroll()
    if not data:
        return {"enrolled": False, "path": str(enroll_path())}
    token = str(data.get("enroll_token") or "")
    masked = (token[:8] + "…") if len(token) > 8 else "…"
    return {
        "enrolled": True,
        "unique_id": data.get("unique_id"),
        "ha_hostname": data.get("ha_hostname") or "",
        "platform_url": data.get("platform_url") or "",
        "enroll_token_prefix": masked,
        "enrolled_at": data.get("enrolled_at") or "",
        "path": str(enroll_path()),
    }


def resolve_credentials() -> tuple[str, str, str]:
    """Return (platform_url, token, appliance_uid). File wins over env for token/uid."""
    env_platform = os.environ.get("BMS_PLATFORM_URL", "http://host.docker.internal:8080").rstrip("/")
    env_token = os.environ.get("BMS_ENROLL_TOKEN", "").strip()
    env_uid = os.environ.get("BMS_APPLIANCE_UID", "").strip()

    data = load_enroll()
    if data:
        platform = str(data.get("platform_url") or "").strip().rstrip("/") or env_platform
        token = str(data.get("enroll_token") or "").strip() or env_token
        uid = str(data.get("unique_id") or data.get("appliance_uid") or "").strip() or env_uid
        return platform, token, uid

    return env_platform, env_token, env_uid
