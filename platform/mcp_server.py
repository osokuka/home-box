"""Home Box MCP server — fast read-only tool surface for OpenClaw and similar agents.

Never calls Home Assistant /api/services. No device control.
SSE: http://<box>:8100/sse
"""

import json
import os

from mcp.server.fastmcp import FastMCP

import ha_readonly

HOST = os.environ.get("BMS_MCP_HOST", "0.0.0.0")
PORT = int(os.environ.get("BMS_MCP_PORT", "8100"))

mcp = FastMCP(
    "Home Box",
    instructions=(
        "Home Box MCP is READ-ONLY status + service catalog. "
        "Use tools to explain the house, never to claim you changed devices. "
        "list_ha_services shows what HA could do; this server cannot execute those services."
    ),
)


def _j(obj) -> str:
    return json.dumps(obj, indent=2, default=str)


@mcp.tool()
def get_box_status() -> str:
    """Box reachability, HA version, location metadata. First call for health checks."""
    return _j(ha_readonly.box_status())


@mcp.tool()
def get_ha_config() -> str:
    """Sanitized HA config: timezone, units, URL labels, sample of loaded components."""
    return _j(ha_readonly.get_ha_config())


@mcp.tool()
def list_ha_services(domain: str = "") -> str:
    """Catalog of HA domains/services (names only). Does NOT execute anything.

    Optional domain filter e.g. climate, light, switch.
    """
    return _j(ha_readonly.list_ha_services(domain or None))


@mcp.tool()
def list_devices(domain: str = "") -> str:
    """List allowed entities with state summaries. Optional domain filter."""
    rows = ha_readonly.list_devices(domain or None)
    return _j({"count": len(rows), "devices": rows})


@mcp.tool()
def get_entity(entity_id: str) -> str:
    """Full safe state+attributes for one entity_id (e.g. climate.heat_pump)."""
    return _j(ha_readonly.get_entity(entity_id))


@mcp.tool()
def get_entities(entity_ids: str = "", domain: str = "") -> str:
    """Batch fetch: comma-separated entity_ids, or all entities in a domain."""
    rows = ha_readonly.get_entities(entity_ids, domain)
    return _j({"count": len(rows), "entities": rows})


@mcp.tool()
def search_entities(query: str, domain: str = "") -> str:
    """Search entity_id / friendly_name substring. Optional domain filter. Max 200 hits."""
    rows = ha_readonly.search_entities(query, domain)
    return _j({"count": len(rows), "query": query, "devices": rows})


@mcp.tool()
def get_climate(entity_id: str = "") -> str:
    """Climate status (mode, temps). Default box climate entity, or * for all."""
    eid = entity_id.strip() or None
    if eid == "*":
        eid = "*"
    rows = ha_readonly.get_climate(eid)
    return _j({"count": len(rows), "climate": rows})


@mcp.tool()
def get_sensors() -> str:
    """All sensor.* summaries (temps, meters, etc.)."""
    rows = ha_readonly._by_domain("sensor")
    return _j({"count": len(rows), "sensors": rows})


@mcp.tool()
def get_binary_sensors() -> str:
    """All binary_sensor.* summaries (faults, contact, motion, etc.)."""
    rows = ha_readonly._by_domain("binary_sensor")
    return _j({"count": len(rows), "binary_sensors": rows})


@mcp.tool()
def get_switches() -> str:
    """All switch.* state summaries (on/off status only — cannot toggle)."""
    rows = ha_readonly._by_domain("switch")
    return _j({"count": len(rows), "switches": rows})


@mcp.tool()
def get_lights() -> str:
    """All light.* state summaries (cannot turn lights on/off)."""
    rows = ha_readonly._by_domain("light")
    return _j({"count": len(rows), "lights": rows})


@mcp.tool()
def get_covers() -> str:
    """All cover.* state summaries (blinds/garage position — cannot move)."""
    rows = ha_readonly._by_domain("cover")
    return _j({"count": len(rows), "covers": rows})


@mcp.tool()
def get_locks() -> str:
    """All lock.* state summaries (locked/unlocked — cannot lock/unlock)."""
    rows = ha_readonly._by_domain("lock")
    return _j({"count": len(rows), "locks": rows})


@mcp.tool()
def get_energy_snapshot() -> str:
    """Heuristic energy/power/gas/water related sensors for explainability."""
    return _j(ha_readonly.get_energy_snapshot())


@mcp.tool()
def get_areas() -> str:
    """Rooms/areas from the area registry."""
    rows = ha_readonly.get_areas()
    return _j({"count": len(rows), "areas": rows})


@mcp.tool()
def get_devices_registry() -> str:
    """Physical/logical devices from device registry (name, model, area)."""
    return _j(ha_readonly.get_devices_registry())


@mcp.tool()
def get_people() -> str:
    """person.* presence states (home/not_home). No account secrets."""
    rows = ha_readonly.get_people()
    return _j({"count": len(rows), "people": rows})


@mcp.tool()
def list_config_entries() -> str:
    """Installed integrations (domain + title only). Useful to see Tuya Local vs cloud Tuya."""
    return _j(ha_readonly.list_config_entries())


def main() -> None:
    print(
        f"home-box-mcp SSE http://{HOST}:{PORT}/sse (read-only status+catalog)",
        flush=True,
    )
    mcp.settings.host = HOST
    mcp.settings.port = PORT
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
