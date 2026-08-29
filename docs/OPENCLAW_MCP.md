# Home Box MCP for AI agents (OpenClaw and others)

Home Box exposes a **read-only** MCP server so agents can inspect status.  
It does **not** turn devices on/off or call Home Assistant services.

## Endpoint (lab)

| | |
| --- | --- |
| URL | `http://127.0.0.1:8100/sse` |
| Transport | MCP SSE |
| Auth | None on lab bind — do not publish this port to the public internet |

Requires `BMS_HA_TOKEN` (long-lived token from Home Box → owner profile) on the `home-box-mcp` compose service.

## Tools

| Tool | Purpose |
| --- | --- |
| `get_box_status` | Box / HA reachability, version |
| `list_devices` | Entities + states (optional `domain` filter) |
| `get_climate` | Climate mode / temperatures |
| `get_areas` | Areas / rooms |

## OpenClaw

Add a remote MCP server pointing at Home Box SSE (adjust host for LAN):

```json5
// ~/.openclaw/openclaw.json (excerpt)
{
  mcp: {
    servers: {
      "home-box": {
        url: "http://127.0.0.1:8100/sse",
      },
    },
  },
}
```

Then verify:

```bash
openclaw mcp probe home-box
openclaw mcp tools
```

Allow MCP tools in the agent/sandbox policy if your OpenClaw build gates `bundle-mcp` (see OpenClaw docs: gateway config-tools).

## Compose

```bash
cd C:\AI\ha
docker compose up -d home-box-mcp
```

Set in `.env`:

```env
BMS_HA_TOKEN=...long-lived-token...
```

## Non-negotiables

- Query / explain only — no equipment commands through MCP.
- No Tuya / OEM clouds as AI providers.
- BYO LLM stays in the **agent** (e.g. OpenClaw model config) for this pass — not a proxy on the box.
- WireGuard remote MCP access is later; lab is LAN / localhost.
