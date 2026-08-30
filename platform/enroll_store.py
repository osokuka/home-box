"""Persist BMS enroll payload on the house box (QR / paste from operator).

File: /config/bms_enroll.json (not committed).

QR shape (v1 enroll-only, v2+ optional WireGuard + optional one-time admin):

  {
    "v": 2,
    "unique_id": "...",
    "enroll_token": "bms_…",
    "ha_hostname": "box-….scardustech.com",
    "platform_url": "http://10.10.0.1",
    "wireguard": { … },
    "admin": { "name": "…", "username": "…", "password": "…" }  // optional, one-time
  }

Admin password is stored only in /config/bms_admin_bootstrap.json (mode 0600),
never in bms_enroll.json or /api/status. Cleared after owner is created.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from wg_store import clear_wg, public_wg_status, save_wg_from_payload

CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
ENROLL_PATH = Path(os.environ.get("BMS_ENROLL_PATH", str(CONFIG / "bms_enroll.json")))
ADMIN_BOOTSTRAP_PATH = Path(
    os.environ.get("BMS_ADMIN_BOOTSTRAP_PATH", str(CONFIG / "bms_admin_bootstrap.json"))
)


def enroll_path() -> Path:
    return ENROLL_PATH


def admin_bootstrap_path() -> Path:
    return ADMIN_BOOTSTRAP_PATH


def extract_admin_credentials(payload: dict[str, Any]) -> dict[str, str] | None:
    """Pull one-time admin credentials from QR. Never log the password."""
    admin = payload.get("admin") or payload.get("owner")
    name = username = password = ""
    if isinstance(admin, dict):
        username = str(admin.get("username") or admin.get("user") or "").strip()
        password = str(admin.get("password") or "").strip()
        name = str(admin.get("name") or admin.get("display_name") or "").strip()
    else:
        username = str(
            payload.get("admin_username") or payload.get("owner_username") or ""
        ).strip()
        password = str(
            payload.get("admin_password") or payload.get("owner_password") or ""
        ).strip()
        name = str(payload.get("admin_name") or payload.get("owner_name") or "").strip()
    if not username or not password:
        return None
    if len(password) < 8:
        raise ValueError("admin.password must be at least 8 characters")
    return {
        "name": name or username,
        "username": username,
        "password": password,
    }


def save_admin_bootstrap(creds: dict[str, str]) -> None:
    path = admin_bootstrap_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    blob = {
        "name": creds["name"],
        "username": creds["username"],
        "password": creds["password"],
        "saved_at": datetime.now(timezone.utc).isoformat(),
    }
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(blob, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)
    try:
        os.chmod(path, 0o600)
    except OSError:
        pass


def load_admin_bootstrap() -> dict[str, str] | None:
    path = admin_bootstrap_path()
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    if not isinstance(data, dict):
        return None
    user = str(data.get("username") or "").strip()
    password = str(data.get("password") or "").strip()
    name = str(data.get("name") or user).strip()
    if not user or not password:
        return None
    return {"name": name, "username": user, "password": password}


def clear_admin_bootstrap() -> bool:
    path = admin_bootstrap_path()
    if path.is_file():
        path.unlink()
        return True
    return False


def has_admin_bootstrap() -> bool:
    return load_admin_bootstrap() is not None


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
    """Normalize and write enroll (+ optional WireGuard + optional admin bootstrap)."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be an object")

    if "enroll_token" not in payload and isinstance(payload.get("qr_payload"), str):
        try:
            nested = json.loads(payload["qr_payload"])
        except Exception as err:
            raise ValueError("qr_payload is not valid JSON") from err
        if isinstance(nested, dict):
            payload = {**nested, **{k: v for k, v in payload.items() if k != "qr_payload"}}

    admin_creds = extract_admin_credentials(payload)

    token = str(payload.get("enroll_token") or "").strip()
    uid = str(payload.get("unique_id") or payload.get("appliance_uid") or "").strip()
    hostname = str(payload.get("ha_hostname") or "").strip()
    platform_url = str(payload.get("platform_url") or "").strip().rstrip("/")

    if not token:
        raise ValueError("enroll_token is required")
    if not uid:
        raise ValueError("unique_id is required")

    wg_meta = None
    if "wireguard" in payload and payload.get("wireguard") is not None:
        wg_meta = save_wg_from_payload(payload)

    version = int(payload.get("v") or 1)
    if wg_meta and version < 2:
        version = 2
    if admin_creds and version < 2:
        version = 2

    body = {
        "v": version,
        "unique_id": uid,
        "appliance_uid": uid,
        "enroll_token": token,
        "ha_hostname": hostname,
        "enrolled_at": datetime.now(timezone.utc).isoformat(),
        "wireguard_configured": bool(wg_meta),
        "admin_bootstrap": bool(admin_creds),
    }
    if platform_url:
        body["platform_url"] = platform_url
    if wg_meta:
        body["wireguard_endpoint"] = wg_meta.get("endpoint") or ""
        body["wireguard_address"] = wg_meta.get("address") or ""

    path = enroll_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(body, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)

    # Drop stale BMS cache from a previous enroll — QR is the source of truth now.
    try:
        from bms_runtime import clear_runtime

        clear_runtime()
    except Exception:
        pass

    if admin_creds:
        save_admin_bootstrap(admin_creds)
    else:
        clear_admin_bootstrap()

    return body


def clear_enroll() -> bool:
    removed = False
    path = enroll_path()
    if path.is_file():
        path.unlink()
        removed = True
    if clear_admin_bootstrap():
        removed = True
    if clear_wg():
        removed = True
    try:
        from bms_runtime import clear_runtime

        if clear_runtime():
            removed = True
    except Exception:
        pass
    return removed


def public_status() -> dict:
    data = load_enroll()
    wg = public_wg_status()
    if not data:
        return {
            "enrolled": False,
            "path": str(enroll_path()),
            "wireguard": wg,
            "admin_bootstrap": False,
        }
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
        "wireguard": wg,
        "admin_bootstrap": has_admin_bootstrap() or bool(data.get("admin_bootstrap")),
    }


def resolve_credentials() -> tuple[str, str, str]:
    """Return (platform_url, token, appliance_uid). File wins over env.

    QR ``platform_url`` always wins when present. Env ``BMS_PLATFORM_URL`` is
    lab fallback only when the enroll file has no platform_url.
    """
    env_platform = os.environ.get("BMS_PLATFORM_URL", "").strip().rstrip("/")
    env_token = os.environ.get("BMS_ENROLL_TOKEN", "").strip()
    env_uid = os.environ.get("BMS_APPLIANCE_UID", "").strip()

    data = load_enroll()
    if data:
        platform = str(data.get("platform_url") or "").strip().rstrip("/") or env_platform
        token = str(data.get("enroll_token") or "").strip() or env_token
        uid = str(data.get("unique_id") or data.get("appliance_uid") or "").strip() or env_uid
        return platform, token, uid

    return env_platform, env_token, env_uid
