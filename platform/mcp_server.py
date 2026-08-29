"""Home Box MCP — dynamic status + device control for OpenClaw.

SSE: http://<box>:8100/sse
Catalogs and control points are discovered live from each HA instance.
Control requires HOME_BOX_MCP_ALLOW_CONTROL=1 and BMS_HA_TOKEN.
"""

import json
import os

from mcp.server.fastmcp import FastMCP

import ha_control
import ha_readonly

HOST = os.environ.get("BMS_MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("BMS_MCP_PORT", "8100"))

_CTRL = (
    "Device control ENABLED (live catalog minus deny list). "
    if ha_control.control_enabled()
    else "Device control DISABLED until HOME_BOX_MCP_ALLOW_CONTROL=1. "
)

mcp = FastMCP(
    "Home Box",
    instructions=(
        "Home Box MCP: every house differs — discover before acting. "
        + _CTRL
        + "Flow: get_box_status → list_domains / search_entities / list_control_points → "
        "describe_service → call_service or turn_on/climate helpers → verify with get_entity. "
        "Never invent entity_ids. Never use Tuya/OEM clouds."
    ),
)


def _j(obj) -> str:
    return json.dumps(obj, indent=2, default=str)


def _tool_error(err: Exception) -> str:
    return _j({"ok": False, "error": str(err)})


# ---- discovery / status ----

@mcp.tool()
def get_box_status() -> str:
    """Box reachability, HA version, whether MCP control is enabled."""
    st = ha_readonly.box_status()
    st["commands_allowed"] = ha_control.control_enabled()
    st["control"] = {"enabled": ha_control.control_enabled()}
    return _j(st)


@mcp.tool()
def get_ha_config() -> str:
    """Sanitized HA config: timezone, units, URL labels, sample components."""
    return _j(ha_readonly.get_ha_config())


@mcp.tool()
def list_domains() -> str:
    """Entity domains present on THIS box with counts (dynamic inventory)."""
    try:
        rows = ha_readonly.list_domains_present()
        return _j({"count": len(rows), "domains": rows, "source": "live:/api/states"})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def list_ha_services(domain: str = "") -> str:
    """Live HA service catalog for this box, with field schemas. Does not execute."""
    try:
        return _j(ha_readonly.list_ha_services(domain or None, include_fields=True))
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def describe_service(domain: str, service: str) -> str:
    """Field schema for one domain.service as registered on this box."""
    try:
        return _j(ha_readonly.describe_service(domain, service))
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def list_devices(domain: str = "") -> str:
    """List entities on this box. Optional domain filter."""
    try:
        rows = ha_readonly.list_devices(domain or None)
        return _j({"count": len(rows), "devices": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_entity(entity_id: str) -> str:
    """Full safe state+attributes for one entity_id."""
    try:
        return _j(ha_readonly.get_entity(entity_id))
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_entities(entity_ids: str = "", domain: str = "") -> str:
    """Batch fetch: comma-separated entity_ids, or all entities in a domain."""
    try:
        rows = ha_readonly.get_entities(entity_ids, domain)
        return _j({"count": len(rows), "entities": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def search_entities(query: str, domain: str = "") -> str:
    """Search entity_id / friendly_name substring on this box. Optional domain filter."""
    try:
        rows = ha_readonly.search_entities(query, domain)
        return _j({"count": len(rows), "query": query, "devices": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_climate(entity_id: str = "") -> str:
    """Climate status. Empty = all climate.* on this box; pass entity_id for one; * = all."""
    try:
        rows = ha_readonly.get_climate(entity_id.strip() or None)
        return _j({"count": len(rows), "climate": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_sensors() -> str:
    """All sensor.* summaries on this box."""
    try:
        rows = ha_readonly._by_domain("sensor")
        return _j({"count": len(rows), "sensors": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_binary_sensors() -> str:
    """All binary_sensor.* summaries on this box."""
    try:
        rows = ha_readonly._by_domain("binary_sensor")
        return _j({"count": len(rows), "binary_sensors": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_switches() -> str:
    """All switch.* state summaries on this box."""
    try:
        rows = ha_readonly._by_domain("switch")
        return _j({"count": len(rows), "switches": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_lights() -> str:
    """All light.* state summaries on this box."""
    try:
        rows = ha_readonly._by_domain("light")
        return _j({"count": len(rows), "lights": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_covers() -> str:
    """All cover.* state summaries on this box."""
    try:
        rows = ha_readonly._by_domain("cover")
        return _j({"count": len(rows), "covers": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_locks() -> str:
    """All lock.* state summaries on this box."""
    try:
        rows = ha_readonly._by_domain("lock")
        return _j({"count": len(rows), "locks": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_energy_snapshot() -> str:
    """Heuristic energy/power related sensors on this box."""
    try:
        return _j(ha_readonly.get_energy_snapshot())
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_areas() -> str:
    """Rooms/areas from the area registry on this box."""
    try:
        rows = ha_readonly.get_areas()
        return _j({"count": len(rows), "areas": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_devices_registry() -> str:
    """Device registry: name, model, area (this box)."""
    try:
        return _j(ha_readonly.get_devices_registry())
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def get_people() -> str:
    """person.* presence states on this box."""
    try:
        rows = ha_readonly.get_people()
        return _j({"count": len(rows), "people": rows})
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def list_config_entries() -> str:
    """Installed integrations on this box (domain + title only)."""
    try:
        return _j(ha_readonly.list_config_entries())
    except Exception as err:
        return _tool_error(err)


# ---- control (dynamic) ----

@mcp.tool()
def get_control_capabilities() -> str:
    """Whether control is on, deny lists, and sample of executable services on THIS box."""
    try:
        return _j(ha_control.control_capabilities())
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def list_control_points(domain: str = "", query: str = "", limit: int = 200) -> str:
    """Controllable entities on THIS box with callable service names (live ∩ deny list)."""
    try:
        return _j(ha_control.list_control_points(domain, query, limit))
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def call_service(domain: str, service: str, entity_id: str = "", data_json: str = "{}") -> str:
    """Execute a service if it exists on this box and is not deny-listed.

    Discover with list_control_points / describe_service first.
    data_json: extra service data as JSON object, e.g. {"temperature": 21}.
    """
    try:
        out = ha_control.call_service(domain, service, entity_id, data_json)
        if entity_id.strip():
            out["verify"] = ha_control.verify_after(entity_id.strip())
        return _j(out)
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def turn_on(entity_id: str) -> str:
    """Turn on entity_id (must exist on this box)."""
    try:
        out = ha_control.turn_on(entity_id)
        out["verify"] = ha_control.verify_after(entity_id)
        return _j(out)
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def turn_off(entity_id: str) -> str:
    """Turn off entity_id."""
    try:
        out = ha_control.turn_off(entity_id)
        out["verify"] = ha_control.verify_after(entity_id)
        return _j(out)
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def toggle(entity_id: str) -> str:
    """Toggle entity_id."""
    try:
        out = ha_control.toggle(entity_id)
        out["verify"] = ha_control.verify_after(entity_id)
        return _j(out)
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def climate_set_temperature(entity_id: str, temperature: float, hvac_mode: str = "") -> str:
    """Set climate setpoint. entity_id required (no default — each box differs)."""
    try:
        out = ha_control.climate_set_temperature(temperature, entity_id, hvac_mode)
        out["verify"] = ha_control.verify_after(entity_id)
        return _j(out)
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def climate_set_hvac_mode(entity_id: str, hvac_mode: str) -> str:
    """Set HVAC mode. entity_id required."""
    try:
        out = ha_control.climate_set_hvac_mode(hvac_mode, entity_id)
        out["verify"] = ha_control.verify_after(entity_id)
        return _j(out)
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def cover_open(entity_id: str) -> str:
    """Open a cover on this box."""
    try:
        out = ha_control.cover_open(entity_id)
        out["verify"] = ha_control.verify_after(entity_id)
        return _j(out)
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def cover_close(entity_id: str) -> str:
    """Close a cover on this box."""
    try:
        out = ha_control.cover_close(entity_id)
        out["verify"] = ha_control.verify_after(entity_id)
        return _j(out)
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def lock_lock(entity_id: str) -> str:
    """Lock a lock entity on this box."""
    try:
        out = ha_control.lock_lock(entity_id)
        out["verify"] = ha_control.verify_after(entity_id)
        return _j(out)
    except Exception as err:
        return _tool_error(err)


@mcp.tool()
def lock_unlock(entity_id: str) -> str:
    """Unlock a lock entity. Only when the user clearly asks."""
    try:
        out = ha_control.lock_unlock(entity_id)
        out["verify"] = ha_control.verify_after(entity_id)
        return _j(out)
    except Exception as err:
        return _tool_error(err)


def main() -> None:
    mode = "control+dynamic" if ha_control.control_enabled() else "status-only"
    print(f"home-box-mcp SSE http://{HOST}:{PORT}/sse ({mode})", flush=True)
    mcp.settings.host = HOST
    mcp.settings.port = PORT
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
