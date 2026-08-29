"""Home Box MCP device control — dynamic per-box, deny-listed for safety.

Executable services = whatever this HA advertises via /api/services,
minus hard-denied domains/services. No fixed product device map.
Requires HOME_BOX_MCP_ALLOW_CONTROL=1 and BMS_HA_TOKEN.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from ha_readonly import (
    DENIED_ENTITY_DOMAINS,
    HA_TOKEN,
    HA_URL,
    describe_service,
    domain_allowed_for_entity,
    fetch_services_catalog,
    get_entity,
    list_devices,
    list_domains_present,
    service_exists,
)

ALLOW_CONTROL = os.environ.get("HOME_BOX_MCP_ALLOW_CONTROL", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "on",
)

# Entire domains blocked even if HA advertises them.
DENIED_SERVICE_DOMAINS = frozenset(
    {
        "hassio",
        "backup",
        "recorder",
        "shell_command",
        "command_line",
        "python_script",
        "rest_command",
        "system_log",
        "ffmpeg",
        "image",
        "conversation",
        "todo",  # often personal; keep status via entities if needed
    }
)

# Specific domain.service blocks (host power / destructive core).
DENIED_SERVICES = frozenset(
    {
        "homeassistant.restart",
        "homeassistant.stop",
        "homeassistant.reboot",
        "homeassistant.reload_all",
        "homeassistant.reload_core_config",
        "homeassistant.reload_config_entry",
        "homeassistant.reload_custom_components",
        "homeassistant.reload_themes",
        "frontend.reload_themes",
        "persistent_notification.create",
        "persistent_notification.dismiss",
        "persistent_notification.dismiss_all",
    }
)

# Domains that usually need an entity_id / target when calling from MCP.
ENTITY_SCOPED_HINT = frozenset(
    {
        "switch",
        "light",
        "fan",
        "cover",
        "lock",
        "climate",
        "water_heater",
        "humidifier",
        "valve",
        "media_player",
        "vacuum",
        "alarm_control_panel",
        "input_boolean",
        "input_number",
        "input_select",
        "input_text",
        "script",
        "scene",
        "button",
        "select",
        "number",
        "remote",
        "siren",
        "lawn_mower",
    }
)


def control_enabled() -> bool:
    return ALLOW_CONTROL


def require_control() -> None:
    if not ALLOW_CONTROL:
        raise RuntimeError(
            "Device control is disabled. Set HOME_BOX_MCP_ALLOW_CONTROL=1 on home-box-mcp."
        )
    if not HA_TOKEN:
        raise RuntimeError("BMS_HA_TOKEN is required for device control.")


def is_service_denied(domain: str, service: str) -> bool:
    domain = (domain or "").strip().lower()
    service = (service or "").strip().lower()
    if domain in DENIED_SERVICE_DOMAINS:
        return True
    if f"{domain}.{service}" in DENIED_SERVICES:
        return True
    # Block any hassio-style host power if domain slips through
    if "reboot" in service or service in ("host_reboot", "host_shutdown", "shutdown"):
        if domain in ("hassio", "homeassistant", "hassio.host"):
            return True
    return False


def is_service_callable(domain: str, service: str) -> bool:
    domain = (domain or "").strip().lower()
    service = (service or "").strip().lower()
    if not domain or not service:
        return False
    if is_service_denied(domain, service):
        return False
    return service_exists(domain, service)


def list_control_points(
    domain: str = "",
    query: str = "",
    limit: int = 200,
) -> dict[str, Any]:
    """Intersect this box's entities with live callable services for each domain."""
    require_control()
    want = (domain or "").strip().lower() or None
    q = (query or "").strip().lower()
    catalog = {b["domain"]: b for b in fetch_services_catalog()}
    ha_block = catalog.get("homeassistant") or {}
    ha_svcs = set(ha_block.get("services") or [])
    points: list[dict[str, Any]] = []
    seen_domains: set[str] = set()

    for ent in list_devices(want):
        eid = ent.get("entity_id") or ""
        dom = ent.get("domain") or ""
        if q and q not in eid.lower() and q not in str(ent.get("friendly_name") or "").lower():
            continue
        services: list[str] = []
        block = catalog.get(dom)
        if block:
            for s in block.get("services") or []:
                if not is_service_denied(dom, s):
                    services.append(s)
        for s in ("turn_on", "turn_off", "toggle", "update_entity"):
            if s in ha_svcs and not is_service_denied("homeassistant", s) and s not in services:
                services.append(s)
        points.append(
            {
                "entity_id": eid,
                "friendly_name": ent.get("friendly_name"),
                "state": ent.get("state"),
                "domain": dom,
                "services": sorted(services),
            }
        )
        seen_domains.add(dom)
        if len(points) >= max(1, min(int(limit or 200), 500)):
            break

    domain_only = []
    for dom, block in sorted(catalog.items()):
        if want and dom != want:
            continue
        if dom in DENIED_SERVICE_DOMAINS or dom in seen_domains:
            continue
        svcs = [s for s in (block.get("services") or []) if not is_service_denied(dom, s)]
        if svcs:
            domain_only.append({"domain": dom, "services": svcs, "entity_count": 0})

    return {
        "control_enabled": True,
        "count": len(points),
        "control_points": points,
        "domains_present": list_domains_present(),
        "domain_level_services": domain_only[:50],
        "source": "live entities ∩ /api/services − deny list",
        "note": "Use describe_service for fields, then call_service. entity_id required for device actions.",
    }


def control_capabilities() -> dict[str, Any]:
    """Dynamic capabilities for this box (not a static product allowlist)."""
    if not ALLOW_CONTROL:
        return {
            "control_enabled": False,
            "note": "Set HOME_BOX_MCP_ALLOW_CONTROL=1 to enable.",
            "denied_domains": sorted(DENIED_SERVICE_DOMAINS),
            "denied_services": sorted(DENIED_SERVICES),
        }
    try:
        catalog = fetch_services_catalog()
        executable = []
        for block in catalog:
            dom = block["domain"]
            if dom in DENIED_SERVICE_DOMAINS:
                continue
            for s in block.get("services") or []:
                if is_service_denied(dom, s):
                    continue
                executable.append(f"{dom}.{s}")
        return {
            "control_enabled": True,
            "executable_service_count": len(executable),
            "executable_services_sample": executable[:120],
            "domains_present": list_domains_present(),
            "denied_domains": sorted(DENIED_SERVICE_DOMAINS),
            "denied_services": sorted(DENIED_SERVICES),
            "denied_entity_domains": sorted(DENIED_ENTITY_DOMAINS),
            "note": "Full set is whatever this HA exposes minus denies. Prefer list_control_points.",
        }
    except Exception as err:
        return {
            "control_enabled": True,
            "error": str(err),
            "denied_domains": sorted(DENIED_SERVICE_DOMAINS),
            "denied_services": sorted(DENIED_SERVICES),
        }


def ha_call_service(domain: str, service: str, data: dict[str, Any] | None = None) -> Any:
    require_control()
    domain = (domain or "").strip().lower()
    service = (service or "").strip().lower()
    if not domain or not service:
        raise RuntimeError("domain and service are required")
    if is_service_denied(domain, service):
        raise RuntimeError(f"Service {domain}.{service} is blocked by Home Box MCP policy")
    if not service_exists(domain, service):
        raise RuntimeError(
            f"Service {domain}.{service} is not registered on this Home Box "
            "(discover with list_ha_services / list_control_points)"
        )

    body = dict(data or {})
    eid = body.get("entity_id")
    if isinstance(eid, str) and "." in eid:
        edom = eid.split(".", 1)[0]
        if not domain_allowed_for_entity(edom):
            raise RuntimeError(f"entity domain '{edom}' is not allowed for MCP control")
    elif domain in ENTITY_SCOPED_HINT and not eid and not body.get("device_id") and not body.get("area_id"):
        raise RuntimeError(
            f"{domain}.{service} usually needs entity_id on this MCP — "
            "resolve via search_entities / list_control_points first"
        )

    payload = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{HA_URL}/api/services/{domain}/{service}",
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {HA_TOKEN}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            raw = resp.read().decode()
            return json.loads(raw) if raw.strip() else {"ok": True}
    except urllib.error.HTTPError as err:
        err_body = err.read().decode(errors="replace")[:400]
        raise RuntimeError(f"HA service {domain}.{service} HTTP {err.code}: {err_body}") from err


def call_service(
    domain: str,
    service: str,
    entity_id: str = "",
    data_json: str = "{}",
) -> dict[str, Any]:
    extra: dict[str, Any] = {}
    raw = (data_json or "{}").strip() or "{}"
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as err:
        raise RuntimeError(f"data_json must be JSON object: {err}") from err
    if parsed is None:
        parsed = {}
    if not isinstance(parsed, dict):
        raise RuntimeError("data_json must be a JSON object")
    extra.update(parsed)
    if entity_id.strip():
        extra["entity_id"] = entity_id.strip()
    result = ha_call_service(domain, service, extra)
    print(
        f"home-box-mcp CONTROL {domain}.{service} entity_id={extra.get('entity_id', '')}",
        flush=True,
    )
    return {
        "ok": True,
        "domain": domain,
        "service": service,
        "data": extra,
        "result": result,
        "note": "Executed against this box's live service catalog (deny-listed).",
    }


def _entity_domain_service(entity_id: str, service: str) -> dict[str, Any]:
    eid = entity_id.strip()
    if "." not in eid:
        raise RuntimeError("entity_id required (discover via search_entities / list_control_points)")
    domain = eid.split(".", 1)[0]
    # Prefer domain-native service; fall back to homeassistant.*
    if service_exists(domain, service):
        return call_service(domain, service, eid)
    if service_exists("homeassistant", service):
        return call_service("homeassistant", service, eid)
    raise RuntimeError(
        f"Neither {domain}.{service} nor homeassistant.{service} exists on this box"
    )


def turn_on(entity_id: str) -> dict[str, Any]:
    return _entity_domain_service(entity_id, "turn_on")


def turn_off(entity_id: str) -> dict[str, Any]:
    return _entity_domain_service(entity_id, "turn_off")


def toggle(entity_id: str) -> dict[str, Any]:
    return _entity_domain_service(entity_id, "toggle")


def climate_set_temperature(
    temperature: float,
    entity_id: str,
    hvac_mode: str = "",
) -> dict[str, Any]:
    eid = (entity_id or "").strip()
    if not eid:
        raise RuntimeError(
            "entity_id required — use search_entities/list_control_points "
            "(no default climate; each box differs)"
        )
    data: dict[str, Any] = {"temperature": float(temperature)}
    if hvac_mode.strip():
        data["hvac_mode"] = hvac_mode.strip()
    return call_service("climate", "set_temperature", eid, json.dumps(data))


def climate_set_hvac_mode(hvac_mode: str, entity_id: str) -> dict[str, Any]:
    eid = (entity_id or "").strip()
    if not eid:
        raise RuntimeError("entity_id required — discover climate.* on this box first")
    return call_service(
        "climate",
        "set_hvac_mode",
        eid,
        json.dumps({"hvac_mode": hvac_mode.strip()}),
    )


def cover_open(entity_id: str) -> dict[str, Any]:
    return call_service("cover", "open_cover", entity_id)


def cover_close(entity_id: str) -> dict[str, Any]:
    return call_service("cover", "close_cover", entity_id)


def lock_lock(entity_id: str) -> dict[str, Any]:
    return call_service("lock", "lock", entity_id)


def lock_unlock(entity_id: str) -> dict[str, Any]:
    return call_service("lock", "unlock", entity_id)


def verify_after(entity_id: str) -> dict[str, Any]:
    try:
        return {"entity": get_entity(entity_id)}
    except Exception as err:
        return {"entity_error": str(err)}


# re-export for mcp_server convenience
__all__ = [
    "ALLOW_CONTROL",
    "call_service",
    "climate_set_hvac_mode",
    "climate_set_temperature",
    "control_capabilities",
    "control_enabled",
    "cover_close",
    "cover_open",
    "describe_service",
    "list_control_points",
    "lock_lock",
    "lock_unlock",
    "toggle",
    "turn_off",
    "turn_on",
    "verify_after",
]
