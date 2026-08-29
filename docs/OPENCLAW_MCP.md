# Home Box MCP — tools, consumption, utilization

MCP for **OpenClaw** and similar agents. Every Home Box has a different IoT mix — **entity and service catalogs are discovered live** from that box’s Home Assistant. There is no fixed device map.

| | |
| --- | --- |
| Endpoint | `http://127.0.0.1:8100/sse` (lab) |
| Transport | MCP SSE |
| Token | `BMS_HA_TOKEN` long-lived HA token |
| Control gate | `HOME_BOX_MCP_ALLOW_CONTROL=1` (default in compose) |

BYO LLM stays in the **agent**. This server exposes house context + guarded local HA actions only — never Tuya/OEM clouds.

---

## Agent loop (required)

1. `get_box_status` — online? `commands_allowed`?
2. `list_domains` / `search_entities` / `list_devices` — what exists **here**
3. `list_control_points` — what can be called for those entities
4. `describe_service` — required fields for that service on this box
5. `call_service` or convenience helper → check `verify` / `get_entity`

Never invent `entity_id` values. Never assume `climate.heat_pump` or any lab name exists on a customer box.

---

## Safety model

- Control off unless `HOME_BOX_MCP_ALLOW_CONTROL` is truthy
- Callable = **live** `/api/services` **minus** deny list (hassio, backup, recorder, shell/rest/python_script, host restart/stop, …)
- Entity domains use a small **deny** list (noise), not a product allowlist
- Control calls log `home-box-mcp CONTROL …`
- Status-only: `HOME_BOX_MCP_ALLOW_CONTROL=0`

---

## Tool reference

### Discovery

| Tool | Consume / utilize |
| --- | --- |
| `get_box_status` | Session start; read `commands_allowed` |
| `list_domains` | Inventory of entity domains + counts on this box |
| `list_ha_services` | Full live service catalog + field schemas |
| `describe_service` | One service’s fields before `call_service` |
| `list_control_points` | Entities × callable services (filtered by domain/query) |
| `get_control_capabilities` | Gate + deny lists + sample executable services |
| `search_entities` / `list_devices` / `get_entity` | Resolve NL → entity_id → state |
| `list_config_entries` / `get_devices_registry` / `get_areas` | Integrations, hardware, rooms |
| Domain getters (`get_climate`, `get_lights`, …) | Convenience reads; empty climate = **all** `climate.*` on this box |

### Control

| Tool | Notes |
| --- | --- |
| `call_service(domain, service, entity_id?, data_json?)` | Primary write path; must exist live and not be denied |
| `turn_on` / `turn_off` / `toggle` | `entity_id` required |
| `climate_set_temperature` / `climate_set_hvac_mode` | **`entity_id` required** (no default) |
| `cover_open` / `cover_close` / `lock_lock` / `lock_unlock` | `entity_id` required |

---

## OpenClaw wiring

```json5
{
  mcp: {
    servers: {
      "home-box": { url: "http://127.0.0.1:8100/sse" },
    },
  },
}
```

```bash
openclaw mcp probe home-box
openclaw mcp tools
```

## Compose

```bash
cd C:\AI\ha
docker compose up -d --force-recreate home-box-mcp
```

```env
BMS_HA_TOKEN=...long-lived-token...
HOME_BOX_MCP_ALLOW_CONTROL=1
# optional hint only — never required by MCP tools:
# BMS_CLIMATE_ENTITY=climate.some_name
```

## Non-negotiables

- Discover per box; do not hardcode customer entity ids in agents
- Local HA services only; no OEM cloud AI path
- No restart / host power / backup / shell via MCP
- Do not publish `:8100` to WAN without auth + VPN
