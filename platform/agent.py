"""Talk to the BMS platform from this box. Read-only.

Loads enroll from /config/bms_enroll.json (first-run UI) or env fallback.
GET subscription + POST heartbeat (+ appliance_uid) + POST device *status*.
Never calls Home Assistant services (no turn_on / set_hvac_mode).
Never contacts device-vendor clouds. Outbound should be LAN/VPN only.
"""

from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

from enroll_store import resolve_credentials

HA_URL = os.environ.get("BMS_HA_URL", "http://homeassistant:8123").rstrip("/")
HA_TOKEN = os.environ.get("BMS_HA_TOKEN", "").strip()
INTERVAL = int(os.environ.get("BMS_INTERVAL", "20"))
VERSION = os.environ.get("BMS_AGENT_VERSION", "ha-lab-0.1")
CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
CLIMATE_ENTITY = os.environ.get("BMS_CLIMATE_ENTITY", "climate.heat_pump")


def api(method: str, path: str, body: dict | None = None) -> dict:
    platform, token, _uid = resolve_credentials()
    if not token:
        raise RuntimeError("no enroll token (save QR on enroll UI or set BMS_ENROLL_TOKEN)")
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        f"{platform}{path}",
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def ha_get(path: str):
    """GET only. This agent must never POST /api/services."""
    if not HA_TOKEN:
        return None
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        headers={"Authorization": f"Bearer {HA_TOKEN}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def read_json_storage(name: str):
    path = CONFIG / ".storage" / name
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def climate_from_restore():
    blob = read_json_storage("core.restore_state")
    data = blob.get("data") if isinstance(blob, dict) else None
    if not isinstance(data, list):
        return None
    for row in data:
        state = row.get("state") if isinstance(row, dict) else None
        if not isinstance(state, dict):
            continue
        if state.get("entity_id") == CLIMATE_ENTITY:
            return state
    return None


def slug_key(name: str, fallback: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")
    return text or fallback


def map_climate(state: dict) -> dict:
    attrs = state.get("attributes") if isinstance(state.get("attributes"), dict) else {}
    ha_state = str(state.get("state") or "unknown")
    if ha_state in ("unavailable", "unknown", ""):
        health = "offline" if ha_state == "unavailable" else "unknown"
        mode = "unknown"
    else:
        health = "online"
        mode = ha_state
    telemetry = {"hvac.mode": mode}
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


def collect_devices() -> list[dict]:
    devices = []
    states = ha_get("/api/states")
    if isinstance(states, list):
        for st in states:
            if not isinstance(st, dict):
                continue
            eid = str(st.get("entity_id") or "")
            if eid.startswith("climate."):
                devices.append(map_climate(st))
    if not devices:
        restored = climate_from_restore()
        if restored:
            devices.append(map_climate(restored))
        else:
            devices.append(
                {
                    "id": "heat-pump",
                    "class": "heat_pump",
                    "system": "hvac",
                    "display_name": "Heat pump",
                    "health": "unknown",
                    "telemetry": {},
                }
            )
    return devices


def loop():
    while True:
        try:
            platform, token, uid = resolve_credentials()
            if not token:
                print("waiting: no enroll token (open enroll UI on :8099)", flush=True)
                time.sleep(INTERVAL)
                continue
            snap = api("GET", "/api/v1/ingest/subscription/")
            fail = bool(snap.get("fail_closed"))
            ha_ok = bool(ha_get("/api/") or (CONFIG / ".storage" / "core.config").is_file())
            hb_body = {
                "version": VERSION,
                "services": [
                    {"id": "homeassistant", "status": "ok" if ha_ok else "down"},
                    {"id": "platform-agent", "status": "ok"},
                ],
            }
            if uid:
                hb_body["appliance_uid"] = uid
            hb = api("POST", "/api/v1/ingest/heartbeat/", hb_body)
            house = (hb.get("household") or {}).get("slug")
            print(
                f"ok slug={house} uid={uid or '-'} live={hb.get('live_status')} "
                f"fail_closed={fail} platform={platform}",
                flush=True,
            )
            if not fail:
                devices = collect_devices()
                posted = api("POST", "/api/v1/ingest/status/", {"devices": devices})
                print(f"status read-only count={posted.get('count')}", flush=True)
        except urllib.error.HTTPError as err:
            body = err.read().decode(errors="replace")
            print("error", {"http": err.code, "body": body[:300]}, flush=True)
        except Exception as err:
            print("error", err, flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    platform, token, uid = resolve_credentials()
    print(
        f"platform-agent ingest {platform} uid={uid or 'unset'} "
        f"token={'set' if token else 'missing'} every {INTERVAL}s (read-only)",
        flush=True,
    )
    loop()
