"""Talk to the BMS platform from this box (sensory feed agent).

Loads enroll from /config/bms_enroll.json (first-run UI) or env fallback.
GET subscription + POST heartbeat (+ appliance_uid).
POST sensory status only when limited share is ON and the feed is positive.
Checks the feed every BMS_INTERVAL seconds (default 5). Idle/empty → no status POST.
Never calls Home Assistant services (no turn_on / set_hvac_mode).
Never contacts device-vendor clouds. Outbound should be LAN/VPN only.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

from bms_fetch import bms_request
from bms_runtime import save_runtime_from_snapshot
from bms_share import limited_share_enabled, load_share
from enroll_store import resolve_credentials
from sensor_feed import collect_devices, collect_support_activity, feed_is_positive

HA_URL = os.environ.get("BMS_HA_URL", "http://homeassistant:8123").rstrip("/")
HA_TOKEN = os.environ.get("BMS_HA_TOKEN", "").strip()
INTERVAL = int(os.environ.get("BMS_INTERVAL", "5"))
# Heartbeat less often than feed checks (default: every 4 ticks ≈ 20s when interval=5).
HEARTBEAT_EVERY = max(1, int(os.environ.get("BMS_HEARTBEAT_EVERY", "4")))
VERSION = os.environ.get("BMS_AGENT_VERSION", "home-box-feed-0.1")
CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
CLIMATE_ENTITY = os.environ.get("BMS_CLIMATE_ENTITY", "climate.heat_pump")


def ha_service_row() -> dict:
    """Probe Home Assistant for heartbeat service list."""
    try:
        req = urllib.request.Request(
            f"{HA_URL}/",
            method="GET",
            headers={"Accept": "text/html,application/json"},
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            code = getattr(resp, "status", 200) or 200
        if 200 <= int(code) < 500:
            return {"id": "homeassistant", "status": "ok", "detail": f"http {code}"}
        return {"id": "homeassistant", "status": "degraded", "detail": f"http {code}"}
    except Exception as err:
        return {"id": "homeassistant", "status": "down", "detail": str(err)[:160]}


def api(method: str, path: str, body: dict | None = None) -> dict:
    return bms_request(method, path, body, timeout=15)


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


def climate_from_restore():
    path = CONFIG / ".storage" / "core.restore_state"
    if not path.is_file():
        return None
    try:
        blob = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
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


def loop() -> None:
    tick = 0
    while True:
        try:
            platform, token, uid = resolve_credentials()
            if not token:
                print("waiting: no enroll token (open enroll UI on :8099)", flush=True)
                time.sleep(INTERVAL)
                continue

            share = load_share()
            share_on = bool(share.get("limited_share_enabled"))
            sensor_entities = list(share.get("sensor_entities") or [])
            do_heartbeat = tick % HEARTBEAT_EVERY == 0
            tick += 1

            snap: dict = {}
            if do_heartbeat:
                snap = api("GET", "/api/v1/ingest/subscription/")
                fail = bool(snap.get("fail_closed"))
                ha_row = ha_service_row()
                scope = share.get("scope") or ["status", "support_activity", "sensors"]
                hb_body = {
                    "version": VERSION,
                    "services": [
                        {
                            "id": "home-box",
                            "status": "ok"
                            if ha_row.get("status") == "ok"
                            else ha_row.get("status") or "degraded",
                            "detail": "appliance",
                        },
                        {"id": "sensory-feed", "status": "ok"},
                        ha_row,
                    ],
                    "limited_share_enabled": share_on,
                    "limited_share_scope": scope,
                }
                if uid:
                    hb_body["appliance_uid"] = uid
                hb = api("POST", "/api/v1/ingest/heartbeat/", hb_body)
                try:
                    save_runtime_from_snapshot(hb if isinstance(hb, dict) else snap)
                except Exception as cache_err:
                    print(f"runtime cache warn: {cache_err}", flush=True)
                house = (hb.get("household") or {}).get("slug")
                reset_flag = bool(
                    ((hb.get("machine") or {}) if isinstance(hb, dict) else {}).get(
                        "allow_password_reset"
                    )
                )
                print(
                    f"ok slug={house} uid={uid or '-'} live={hb.get('live_status')} "
                    f"fail_closed={fail} pwd_reset={reset_flag} "
                    f"limited_share={share_on} platform={platform}",
                    flush=True,
                )
                if fail:
                    time.sleep(INTERVAL)
                    continue
            else:
                fail = False

            if fail:
                time.sleep(INTERVAL)
                continue

            if not share_on:
                if do_heartbeat:
                    print(
                        "limited share OFF — sensory feed not posted "
                        "(enable under Company access on Home Box)",
                        flush=True,
                    )
                time.sleep(INTERVAL)
                continue

            states = ha_get("/api/states")
            state_list = states if isinstance(states, list) else None
            if not state_list:
                restored = climate_from_restore()
                state_list = [restored] if restored else []

            devices = collect_devices(
                state_list,
                climate_entity=CLIMATE_ENTITY,
                sensor_entities=sensor_entities,
                include_climate=True,
            )
            if not feed_is_positive(devices):
                print(
                    f"feed idle — not posting "
                    f"(devices={len(devices)} sensors={len(sensor_entities)})",
                    flush=True,
                )
                time.sleep(INTERVAL)
                continue

            activity = collect_support_activity(state_list)
            posted = api(
                "POST",
                "/api/v1/ingest/status/",
                {
                    "devices": devices,
                    "support_activity": activity,
                    "limited_share": True,
                    "feed": "sensory",
                },
            )
            print(
                f"feed positive count={posted.get('count')} "
                f"devices={len(devices)} activity={len(activity)}",
                flush=True,
            )
        except urllib.error.HTTPError as err:
            body = err.read().decode(errors="replace")
            print("error", {"http": err.code, "body": body[:300]}, flush=True)
        except Exception as err:
            print("error", err, flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    platform, token, uid = resolve_credentials()
    print(
        f"sensory-feed ingest {platform} uid={uid or 'unset'} "
        f"token={'set' if token else 'missing'} every {INTERVAL}s "
        f"(status only when share ON and feed positive)",
        flush=True,
    )
    loop()
