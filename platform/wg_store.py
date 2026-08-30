"""WireGuard peer config from BMS enroll QR (Home Box side).

QR may include optional ``wireguard`` for the **box** peer only.
Private keys are stored under /config/wireguard/ — never re-echoed to the UI.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

CONFIG = Path(os.environ.get("HA_CONFIG", "/config"))
WG_DIR = Path(os.environ.get("BMS_WG_DIR", str(CONFIG / "wireguard")))
WG_CONF = WG_DIR / "wg0.conf"
WG_META = WG_DIR / "meta.json"


def wg_conf_path() -> Path:
    return WG_CONF


def has_wg_conf() -> bool:
    return WG_CONF.is_file() and WG_CONF.stat().st_size > 0


def clear_wg() -> bool:
    removed = False
    for path in (WG_CONF, WG_META, WG_DIR / "wg_confs" / "wg0.conf", WG_DIR / "APPLY_REQUESTED"):
        if path.is_file():
            path.unlink()
            removed = True
    return removed


def _pick_box_peer(wg: dict[str, Any]) -> dict[str, Any] | None:
    """Accept either a single peer object or prepare-box ``peers`` list."""
    if not isinstance(wg, dict):
        return None
    peers = wg.get("peers")
    if isinstance(peers, list):
        for peer in peers:
            if not isinstance(peer, dict):
                continue
            role = str(peer.get("role") or "").lower()
            label = str(peer.get("label") or "").lower()
            if role in ("box", "ha", "home_box", "appliance") or "box" in label or "ha " in label:
                return {**wg, **peer}
        # Fallback: first peer if only one
        if len(peers) == 1 and isinstance(peers[0], dict):
            return {**wg, **peers[0]}
        return None
    return wg


def build_conf(wg: dict[str, Any]) -> str:
    """Build a WireGuard client conf from QR wireguard object."""
    peer = _pick_box_peer(wg)
    if not peer:
        raise ValueError("wireguard: no box peer found (need role=box or config)")

    raw_conf = peer.get("config")
    if isinstance(raw_conf, str) and "[Interface]" in raw_conf:
        text = raw_conf.strip().replace("\r\n", "\n") + "\n"
        if "PrivateKey" not in text:
            raise ValueError("wireguard.config missing PrivateKey")
        return text

    priv = str(peer.get("private_key") or "").strip()
    address = str(peer.get("address") or "").strip()
    server_pub = str(
        peer.get("server_public_key")
        or peer.get("peer_public_key")
        or wg.get("server_public_key")
        or ""
    ).strip()
    endpoint = str(peer.get("endpoint") or wg.get("endpoint") or "").strip()
    allowed = str(
        peer.get("allowed_ips") or wg.get("allowed_ips") or "10.10.0.0/16"
    ).strip()
    keepalive = peer.get("persistent_keepalive")
    if keepalive is None:
        keepalive = wg.get("persistent_keepalive", 25)

    if not priv or not address or not server_pub or not endpoint:
        raise ValueError(
            "wireguard needs config=… or private_key+address+server_public_key+endpoint"
        )

    lines = [
        "# Home Box — written from BMS enroll QR. Do not commit.",
        "[Interface]",
        f"PrivateKey = {priv}",
        f"Address = {address if '/' in address else address + '/32'}",
        "",
        "[Peer]",
        f"PublicKey = {server_pub}",
        f"Endpoint = {endpoint}",
        f"AllowedIPs = {allowed}",
        f"PersistentKeepalive = {int(keepalive)}",
        "",
    ]
    return "\n".join(lines)


def _meta_from_conf(conf: str, wg: dict[str, Any]) -> dict[str, Any]:
    endpoint = ""
    address = ""
    for line in conf.splitlines():
        if line.startswith("Endpoint"):
            endpoint = line.split("=", 1)[-1].strip()
        if line.startswith("Address"):
            address = line.split("=", 1)[-1].strip()
    peer = _pick_box_peer(wg) or {}
    return {
        "endpoint": endpoint or str(wg.get("endpoint") or ""),
        "address": address or str(peer.get("address") or ""),
        "role": str(peer.get("role") or "box"),
        "label": str(peer.get("label") or "HA box"),
        "has_private_key": "PrivateKey" in conf,
    }


def save_wg_from_payload(payload: dict[str, Any]) -> dict[str, Any] | None:
    """If payload has wireguard, write wg0.conf. Return public meta or None if absent."""
    wg = payload.get("wireguard")
    if wg is None:
        return None
    if not isinstance(wg, dict):
        raise ValueError("wireguard must be an object")

    conf = build_conf(wg)
    WG_DIR.mkdir(parents=True, exist_ok=True)
    tmp = WG_CONF.with_suffix(".tmp")
    tmp.write_text(conf, encoding="utf-8")
    tmp.replace(WG_CONF)
    try:
        os.chmod(WG_CONF, 0o600)
    except OSError:
        pass

    meta = _meta_from_conf(conf, wg)
    meta_path = WG_META
    meta_tmp = meta_path.with_suffix(".tmp")
    import json

    meta_tmp.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    meta_tmp.replace(meta_path)
    _sync_linuxserver_layout()
    return meta


def _sync_linuxserver_layout() -> None:
    """linuxserver/wireguard reads /config/wg_confs/*.conf inside the container."""
    if not has_wg_conf():
        return
    confs = WG_DIR / "wg_confs"
    confs.mkdir(parents=True, exist_ok=True)
    target = confs / "wg0.conf"
    text = WG_CONF.read_text(encoding="utf-8")
    tmp = target.with_suffix(".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(target)
    try:
        os.chmod(target, 0o600)
    except OSError:
        pass


def apply_wireguard() -> dict[str, Any]:
    """Ensure conf is ready; restart or create the WireGuard client container."""
    import json
    import subprocess
    import time

    if not has_wg_conf():
        return {"ok": False, "error": "no_wg_conf", "configured": False}

    _sync_linuxserver_layout()
    flag = WG_DIR / "APPLY_REQUESTED"
    flag.write_text(f"{int(time.time())}\n", encoding="utf-8")

    root = Path(os.environ.get("HOME_BOX_ROOT", "/workspace"))
    service = os.environ.get("HOME_BOX_WG_SERVICE", "wireguard").strip() or "wireguard"
    container = os.environ.get("HOME_BOX_WG_CONTAINER", "home-box-wireguard").strip()
    enroll_name = os.environ.get("HOME_BOX_ENROLL_CONTAINER", "home-box-enroll").strip()
    image = os.environ.get(
        "HOME_BOX_WG_IMAGE",
        "lscr.io/linuxserver/wireguard:1.0.20210914-r4-ls50",
    ).strip()
    sock = Path("/var/run/docker.sock")

    result: dict[str, Any] = {
        "ok": True,
        "configured": True,
        "path": str(WG_CONF),
        "mode": "conf_ready",
        "service": service,
        "container": container,
    }

    if not sock.exists():
        result["mode"] = "conf_ready_no_docker_sock"
        result["hint"] = (
            "WireGuard conf saved. On Linux/Pi run: "
            "docker compose --profile wireguard up -d --force-recreate wireguard. "
            "On Windows lab import config/wireguard/wg0.conf into WireGuard for Windows."
        )
        return result

    def _run(cmd: list[str], timeout: int = 120) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd,
            cwd=str(root) if root.is_dir() else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )

    def _host_wg_bind() -> tuple[str | None, str | None]:
        """Resolve host path for wireguard conf + docker network from enroll container."""
        env_bind = os.environ.get("HOME_BOX_HOST_WG_DIR", "").strip()
        insp = _run(["docker", "inspect", enroll_name], timeout=20)
        if insp.returncode != 0:
            return (env_bind or None), None
        try:
            info = json.loads(insp.stdout or "[]")[0]
        except Exception:
            return (env_bind or None), None
        host_config = ""
        for m in info.get("Mounts") or []:
            if m.get("Destination") == "/config" and m.get("Source"):
                host_config = str(m["Source"])
                break
        host_wg = env_bind
        if not host_wg and host_config:
            # Windows + Linux host paths both join with the last segment
            if "\\" in host_config:
                host_wg = host_config.rstrip("\\") + "\\wireguard"
            else:
                host_wg = host_config.rstrip("/") + "/wireguard"
        nets = list((info.get("NetworkSettings") or {}).get("Networks") or {})
        network = nets[0] if nets else None
        return host_wg or None, network

    def _create_wg_container() -> subprocess.CompletedProcess[str]:
        host_wg, network = _host_wg_bind()
        if not host_wg:
            return subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="cannot resolve host wireguard bind path from enroll /config mount",
            )
        cmd = [
            "docker",
            "run",
            "-d",
            "--name",
            container,
            "--restart",
            "unless-stopped",
            "--cap-add",
            "NET_ADMIN",
            "--cap-add",
            "SYS_MODULE",
            "--sysctl",
            "net.ipv4.conf.all.src_valid_mark=1",
            "-e",
            f"TZ={os.environ.get('TZ', 'Europe/Amsterdam')}",
            "-e",
            "PUID=0",
            "-e",
            "PGID=0",
            "-v",
            f"{host_wg}:/config",
            "-v",
            "/lib/modules:/lib/modules:ro",
            "--label",
            "com.docker.compose.service=wireguard",
            "--label",
            "home-box.wireguard=1",
        ]
        if network:
            cmd.extend(["--network", network])
        cmd.append(image)
        result["host_wg_bind"] = host_wg
        result["network"] = network or ""
        return _run(cmd, timeout=120)

    try:
        inspect = _run(["docker", "inspect", "-f", "{{.State.Running}}", container], timeout=20)
        if inspect.returncode == 0:
            running = (inspect.stdout or "").strip().lower() == "true"
            if not running:
                _run(["docker", "start", container], timeout=60)
            restart = _run(["docker", "restart", container], timeout=60)
            result["exit_code"] = restart.returncode
            result["stdout"] = (restart.stdout or "")[-800:]
            result["stderr"] = (restart.stderr or "")[-800:]
            if restart.returncode == 0:
                result["mode"] = "restarted"
                result["hint"] = "WireGuard container restarted with new keys."
                time.sleep(2)
                result["ha_proxy"] = ensure_wg_ha_proxy(_run)
                if not result["ha_proxy"].get("ok"):
                    result["hint"] += " HA proxy on :8123 failed — edge may 502 until fixed."
                else:
                    result["hint"] += " HA published on WG :8123."
                return result
            result["mode"] = "conf_ready_restart_failed"
            result["hint"] = (
                "Conf saved but docker restart failed. "
                "On the host: docker compose --profile wireguard up -d --force-recreate wireguard"
            )
            return result

        # Container missing (e.g. after clear enroll) — create with host bind from enroll mount.
        created = _create_wg_container()
        result["exit_code"] = created.returncode
        result["stdout"] = (created.stdout or "")[-800:]
        result["stderr"] = (created.stderr or "")[-800:]
        if created.returncode == 0:
            result["mode"] = "created"
            result["hint"] = "WireGuard container created with new keys."
            time.sleep(3)
            result["ha_proxy"] = ensure_wg_ha_proxy(_run)
            if not result["ha_proxy"].get("ok"):
                result["hint"] += " HA proxy on :8123 failed — edge may 502 until fixed."
            else:
                result["hint"] += " HA published on WG :8123."
            return result
        result["mode"] = "conf_ready_create_failed"
        result["hint"] = (
            "Conf saved but could not create WireGuard container. "
            f"{(created.stderr or '').strip() or 'unknown error'} "
            "On the host: docker compose --profile wireguard up -d."
        )
        return result
    except FileNotFoundError:
        result["mode"] = "conf_ready_no_docker_cli"
        result["hint"] = "Conf saved; docker CLI missing in enroll container."
        return result
    except Exception as err:
        result["mode"] = "conf_ready_error"
        result["hint"] = f"Conf saved; apply error: {err}"
        return result


def public_wg_status() -> dict[str, Any]:
    if not has_wg_conf():
        return {"configured": False, "path": str(WG_CONF)}
    meta: dict[str, Any] = {}
    if WG_META.is_file():
        try:
            import json

            loaded = json.loads(WG_META.read_text(encoding="utf-8"))
            if isinstance(loaded, dict):
                meta = loaded
        except Exception:
            meta = {}
    # Never expose private key
    return {
        "configured": True,
        "path": str(WG_CONF),
        "endpoint": meta.get("endpoint") or "",
        "address": meta.get("address") or "",
        "role": meta.get("role") or "box",
        "label": meta.get("label") or "",
        "apply_hint": (
            "After QR save, enroll UI creates/restarts WireGuard and waits up to 45s for BMS. "
            "Hello to 10.10.* uses the WG container netns."
        ),
    }


def redact_conf_for_log(conf: str) -> str:
    return re.sub(
        r"(PrivateKey\s*=\s*)\S+",
        r"\1***",
        conf,
        flags=re.IGNORECASE,
    )


WG_HA_PROXY = os.environ.get("HOME_BOX_WG_HA_PROXY", "home-box-wg-ha-proxy").strip()
WG_HA_PROXY_IMAGE = os.environ.get(
    "HOME_BOX_WG_HA_PROXY_IMAGE", "alpine/socat:1.8.0.0"
).strip()
HA_PROXY_TARGET = os.environ.get("HOME_BOX_HA_PROXY_TARGET", "homeassistant:8123").strip()


def ensure_wg_ha_proxy(run_cmd) -> dict[str, Any]:
    """Forward WG-netns :8123 → Home Assistant so edge can reach the box over overlay."""
    container = os.environ.get("HOME_BOX_WG_CONTAINER", "home-box-wireguard").strip()
    # network_mode=container:WG dies across WG restarts — always recreate.
    run_cmd(["docker", "rm", "-f", WG_HA_PROXY], timeout=30)
    create = run_cmd(
        [
            "docker",
            "run",
            "-d",
            "--name",
            WG_HA_PROXY,
            "--restart",
            "unless-stopped",
            "--network",
            f"container:{container}",
            "--label",
            "home-box.wg-ha-proxy=1",
            WG_HA_PROXY_IMAGE,
            "TCP-LISTEN:8123,fork,reuseaddr,bind=0.0.0.0",
            f"TCP:{HA_PROXY_TARGET}",
        ],
        timeout=60,
    )
    return {
        "ok": create.returncode == 0,
        "exit_code": create.returncode,
        "stdout": (create.stdout or "")[-400:],
        "stderr": (create.stderr or "")[-400:],
        "proxy": WG_HA_PROXY,
        "target": HA_PROXY_TARGET,
    }
