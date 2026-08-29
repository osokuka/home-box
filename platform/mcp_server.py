"""Home Box MCP server — read-only tools for agents (OpenClaw, etc.).

Never calls Home Assistant /api/services. No device control.
Transport: SSE on BMS_MCP_PORT (default 8100) → http://<box>:8100/sse
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
        "Home Box status tools are READ-ONLY. You may inspect climate, sensors, "
        "and areas. You must NOT claim you can turn devices on/off or change HVAC "
        "setpoints through these tools — that is not available."
    ),
)


@mcp.tool()
def get_box_status() -> str:
    """Return Home Box / Home Assistant reachability and version (read-only)."""
    return json.dumps(ha_readonly.box_status(), indent=2)


@mcp.tool()
def list_devices(domain: str = "") -> str:
    """List allowed entities and their states.

    Optional domain filter: climate, sensor, binary_sensor, switch, etc.
    Empty domain = all allowed domains. Read-only.
    """
    rows = ha_readonly.list_devices(domain or None)
    return json.dumps({"count": len(rows), "devices": rows}, indent=2)


@mcp.tool()
def get_climate(entity_id: str = "") -> str:
    """Get climate entity status (mode, temps). Default entity from box config.

    Pass entity_id like climate.heat_pump, or * for all climate entities.
    Read-only — cannot change setpoints or HVAC mode.
    """
    eid = entity_id.strip() or None
    if eid == "*":
        eid = "*"
    rows = ha_readonly.get_climate(eid)
    return json.dumps({"count": len(rows), "climate": rows}, indent=2)


@mcp.tool()
def get_areas() -> str:
    """List Home Box areas/rooms (read-only)."""
    rows = ha_readonly.get_areas()
    return json.dumps({"count": len(rows), "areas": rows}, indent=2)


def main() -> None:
    print(
        f"home-box-mcp SSE http://{HOST}:{PORT}/sse (read-only HA tools)",
        flush=True,
    )
    mcp.settings.host = HOST
    mcp.settings.port = PORT
    mcp.run(transport="sse")


if __name__ == "__main__":
    main()
