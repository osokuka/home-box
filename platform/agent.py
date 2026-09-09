"""Talk to the BMS platform from this box (sensory feed agent).

Loads enroll from /config/bms_enroll.json (first-run UI) or env fallback.
GET subscription + POST heartbeat (+ appliance_uid).
POST sensory status when:
  - box share allowlist / toggle changes (always push updated list), or
  - share is ON and the feed is positive

BMS auth = enroll token only. When sensory share is enabled, Home Box auto-creates
a local HA long-lived read token (bms_ha_token in secrets) for friendly names and
live states. Optional BMS_HA_TOKEN env still works as override.
Never calls Home Assistant services. Never contacts device-vendor clouds.
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
from bms_share import load_share
from enroll_store import resolve_credentials
from ha_local import load_local_states, merge_ha_states
from ha_token import resolve_ha_token
from sensor_feed import (
    collect_devices,
    collect_support_activity,
    share_signature,
    should_post_feed,
)

HA_URL = os.environ.get("BMS_HA_URL", "http://homeassistant:8123").rstrip("/")
INTERVAL = int(os.environ.get("BMS_INTERVAL", "5"))
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


def ha_get(path: str, token: str):
    """GET only. This agent must never POST /api/services."""
    if not token:
        return None
    req = urllib.request.Request(
        f"{HA_URL}{path}",
        headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception:
        return None


def loop() -> None:
    tick = 0
    last_share_sig = ""
    while True:
        try:
            platform, token, uid = resolve_credentials()
            if not token:
                print("waiting: no enroll token (open enroll UI on :8099)", flush=True)
                time.sleep(INTERVAL)
                continue

            # Optional: same token MCP/tuya use. Sensory feed does not require it.
            ha_token = resolve_ha_token()
            share = load_share()
            share_on = bool(share.get("limited_share_enabled"))
            sensor_entries = list(share.get("sensors") or [])
            sensor_entities = list(share.get("sensor_entities") or [])
            sig = share_signature(share)
            share_changed = sig != last_share_sig
            do_heartbeat = tick % HEARTBEAT_EVERY == 0
            tick += 1

            local_states = load_local_states(CONFIG)
            feed_detail = "local_ha_storage" if local_states else "no_ha_storage"
            if ha_token:
                feed_detail = "ha_api+local"

            snap: dict = {}
            fail = False
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
                        {
                            "id": "sensory-feed",
                            "status": "ok" if local_states or ha_token else "degraded",
                            "detail": feed_detail,
                        },
                        ha_row,
                    ],
                    "limited_share_enabled": share_on,
                    "limited_share_scope": scope,
                    "sensor_share_count": len(sensor_entries),
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
                    f"limited_share={share_on} sensors={len(sensor_entries)} "
                    f"feed={feed_detail} platform={platform}",
                    flush=True,
                )

            if fail:
                time.sleep(INTERVAL)
                continue

            live = ha_get("/api/states", ha_token)
            live_list = live if isinstance(live, list) else None
            state_list = merge_ha_states(local_states, live_list)

            include_climate = not share_changed
            devices = collect_devices(
                state_list,
                climate_entity=CLIMATE_ENTITY,
                sensors=sensor_entries if share_on else [],
                include_climate=include_climate and share_on,
            )
            # Do not invent domains — omit binary sensors the client has not classified.
            devices = [
                d
                for d in devices
                if d.get("class") != "binary_input" or str(d.get("system") or "").strip()
            ]
            post, reason = should_post_feed(
                share_on=share_on,
                share_changed=share_changed,
                devices=devices,
                sensor_entities=sensor_entities,
            )
            if not post:
                if reason != "share_off" or do_heartbeat:
                    print(
                        f"feed skip reason={reason} "
                        f"devices={len(devices)} sensors={len(sensor_entries)}",
                        flush=True,
                    )
                time.sleep(INTERVAL)
                continue

            activity = collect_support_activity(state_list) if share_on else []
            body = {
                "devices": devices,
                "support_activity": activity,
                "limited_share": share_on,
            }
            try:
                posted = api("POST", "/api/v1/ingest/status/", body)
            except Exception as batch_err:
                if len(devices) <= 1:
                    raise batch_err
                print(
                    f"feed batch failed ({batch_err}); retrying per device "
                    f"({len(devices)})",
                    flush=True,
                )
                ok_n = 0
                for device in devices:
                    try:
                        one = api(
                            "POST",
                            "/api/v1/ingest/status/",
                            {
                                "devices": [device],
                                "support_activity": activity if ok_n == 0 else [],
                                "limited_share": share_on,
                            },
                        )
                        ok_n += int(one.get("count") or 1)
                        print(
                            f"feed device ok id={device.get('id')} "
                            f"system={device.get('system')!r} "
                            f"name={device.get('display_name')!r}",
                            flush=True,
                        )
                    except Exception as one_err:
                        print(
                            f"feed device rejected id={device.get('id')} "
                            f"system={device.get('system')!r}: {one_err}",
                            flush=True,
                        )
                if ok_n == 0 and devices:
                    raise batch_err
                posted = {"count": ok_n, "partial": True}
            print(
                f"feed push reason={reason} count={posted.get('count')} "
                f"devices={len(devices)} sensors={len(sensor_entries)} "
                f"activity={len(activity)}"
                + (" partial=1" if posted.get("partial") else ""),
                flush=True,
            )
            last_share_sig = sig
        except urllib.error.HTTPError as err:
            body = err.read().decode(errors="replace")
            print("error", {"http": err.code, "body": body[:300]}, flush=True)
        except Exception as err:
            print("error", err, flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    platform, token, uid = resolve_credentials()
    local_n = len(load_local_states(CONFIG))
    print(
        f"sensory-feed ingest {platform} uid={uid or 'unset'} "
        f"enroll_token={'set' if token else 'missing'} "
        f"local_ha_entities={local_n} every {INTERVAL}s "
        f"(BMS enroll token only; HA names from /config storage)",
        flush=True,
    )
    loop()
