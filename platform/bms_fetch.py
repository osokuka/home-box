"""HTTP to BMS — direct or via WireGuard container netns.

Overlay addresses (10.10.*) are only reachable from the WG client netns.
Enroll UI and platform-agent must not use host.docker.internal when the QR
carries an overlay platform_url.
"""

from __future__ import annotations

import json
import os
import subprocess
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from enroll_store import resolve_credentials
from wg_store import has_wg_conf

WG_CONTAINER = os.environ.get("HOME_BOX_WG_CONTAINER", "home-box-wireguard").strip()


def _overlay_host(platform: str) -> bool:
    host = (urlparse(platform).hostname or "").strip().lower()
    return host.startswith("10.10.")


def use_wg_netns(platform: str) -> bool:
    """True when BMS is on the WireGuard overlay and conf exists."""
    return bool(platform) and _overlay_host(platform) and has_wg_conf()


def _direct(method: str, url: str, token: str, body: dict | None, timeout: int) -> dict[str, Any]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw.strip() else {}


def _via_wg(method: str, url: str, token: str, body: dict | None, timeout: int) -> dict[str, Any]:
    """Run curl inside the WireGuard container so traffic uses the tunnel."""
    cmd = [
        "docker",
        "exec",
        WG_CONTAINER,
        "curl",
        "-sS",
        "-f",
        "--max-time",
        str(max(1, int(timeout))),
        "-X",
        method,
        "-H",
        f"Authorization: Bearer {token}",
        "-H",
        "Accept: application/json",
        "-H",
        "Content-Type: application/json",
    ]
    if body is not None:
        cmd.extend(["--data-binary", json.dumps(body)])
    cmd.append(url)
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout + 5,
            check=False,
        )
    except FileNotFoundError as err:
        raise RuntimeError("docker CLI missing; cannot reach BMS via WireGuard netns") from err
    except subprocess.TimeoutExpired as err:
        raise TimeoutError(f"BMS via WG timed out: {url}") from err

    if proc.returncode != 0:
        err = (proc.stderr or proc.stdout or "").strip()[:400]
        raise RuntimeError(
            f"BMS via WG failed (exit {proc.returncode}): {err or 'no output'} [{url}]"
        )
    raw = (proc.stdout or "").strip()
    return json.loads(raw) if raw else {}


def bms_request(
    method: str,
    path: str,
    body: dict | None = None,
    *,
    timeout: int = 15,
) -> dict[str, Any]:
    """Call BMS API. Uses WG container netns for 10.10.* platform_url."""
    platform, token, _uid = resolve_credentials()
    if not token:
        raise RuntimeError("no enroll token (save QR on enroll UI or set BMS_ENROLL_TOKEN)")
    platform = platform.rstrip("/")
    if not platform:
        raise RuntimeError("no platform_url (QR must include platform_url)")
    url = f"{platform}{path if path.startswith('/') else '/' + path}"
    if use_wg_netns(platform):
        return _via_wg(method.upper(), url, token, body, timeout)
    return _direct(method.upper(), url, token, body, timeout)


def _readiness(snap: dict[str, Any]) -> tuple[str, str]:
    """Return (state, notification) from subscription snapshot.

    ``state`` is ``standby`` while BMS finishes edge/hostname work, or ``ok``
    when the box may redirect to the public URL. Missing gate fields default
    to ``ok`` (backward compatible with older BMS snapshots).
    """
    machine = snap.get("machine") if isinstance(snap.get("machine"), dict) else {}
    top_status = str(snap.get("status") or "").strip().lower()
    candidates = [
        snap.get("enroll_status"),
        snap.get("enroll_gate"),
        snap.get("public_access"),
        snap.get("bms_hello"),
        top_status if top_status in ("standby", "ok", "ready", "pending", "provisioning", "waiting") else None,
        machine.get("edge_status"),
        machine.get("public_access"),
        machine.get("enroll_status"),
        machine.get("enroll_gate"),
    ]
    notification = (
        snap.get("notification")
        or snap.get("enroll_message")
        or snap.get("message")
        or machine.get("notification")
        or machine.get("enroll_message")
        or machine.get("message")
        or ""
    )
    note = str(notification).strip()
    for raw in candidates:
        if raw is None or raw is False:
            continue
        if raw is True:
            return "ok", note
        val = str(raw).strip().lower()
        if val in ("standby", "pending", "provisioning", "waiting", "not_ready", "busy"):
            return "standby", note or "Standby: BMS is finishing setup. Do not leave this page."
        if val in ("ok", "ready", "available", "done"):
            return "ok", note
    return "ok", note


def bms_hello() -> dict[str, Any]:
    """GET subscription snapshot; normalize enroll-ui hello response.

    ``ok`` is True only when BMS reports ready to redirect (not merely reachable).
    ``bms_hello`` is ``failed`` | ``standby`` | ``ok``.
    """
    platform, token, _uid = resolve_credentials()
    if not token:
        return {
            "ok": False,
            "reachable": False,
            "error": "not_enrolled",
            "bms_hello": "failed",
        }
    platform = (platform or "").rstrip("/")
    if not platform:
        return {
            "ok": False,
            "reachable": False,
            "error": "no platform_url in enroll (QR must include platform_url)",
            "bms_hello": "failed",
        }
    via = "wg" if use_wg_netns(platform) else "direct"
    try:
        snap = bms_request("GET", "/api/v1/ingest/subscription/", timeout=15)
    except urllib.error.HTTPError as err:
        body = err.read().decode(errors="replace")[:300]
        return {
            "ok": False,
            "reachable": False,
            "error": f"BMS HTTP {err.code}: {body}",
            "bms_hello": "failed",
            "platform_url": platform,
            "via": via,
        }
    except Exception as err:
        return {
            "ok": False,
            "reachable": False,
            "error": str(err),
            "bms_hello": "failed",
            "platform_url": platform,
            "via": via,
        }

    state, notification = _readiness(snap if isinstance(snap, dict) else {})
    machine = snap.get("machine") if isinstance(snap.get("machine"), dict) else {}
    household = snap.get("household") if isinstance(snap.get("household"), dict) else {}
    ha_hostname = str(
        machine.get("ha_hostname") or household.get("ha_hostname") or ""
    ).strip()
    return {
        "ok": state == "ok",
        "reachable": True,
        "bms_hello": state,
        "notification": notification,
        "slug": household.get("slug"),
        "ha_hostname": ha_hostname,
        "handover_state": machine.get("handover_state"),
        "allow_password_reset": bool(machine.get("allow_password_reset")),
        "unique_id": snap.get("unique_id") or snap.get("appliance_uid"),
        "platform_url": platform,
        "via": via,
    }
