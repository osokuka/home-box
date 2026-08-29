# Home Box MCP — tools, consumption, utilization

Read-only MCP for **OpenClaw** and similar agents.  
**No device control** — agents may inspect and explain, never call HA services through this server.

| | |
| --- | --- |
| Endpoint | `http://127.0.0.1:8100/sse` (lab) |
| Transport | MCP SSE |
| Auth | Lab open on bind — do not expose to WAN |
| Token | `BMS_HA_TOKEN` long-lived HA token on `home-box-mcp` |

BYO LLM stays in the **agent** (OpenClaw model config). This server only supplies house context.

---

## How agents should consume tools

Typical agent loop:

1. `get_box_status` — is the box online?
2. `list_config_entries` / `get_areas` / `get_devices_registry` — what exists?
3. `search_entities` or domain tools — find the thing the user asked about
4. `get_entity` / `get_climate` — precise answer
5. `list_ha_services` — only to explain *what HA could do*; never claim you did it

Always tell the user that changes require a human in the Home Box UI (or a future guarded control API).

---

## Tool reference

### System

#### `get_box_status`
| | |
| --- | --- |
| **Returns** | Product name, HA reachability, version, location/timezone snippet, `commands_allowed: false` |
| **Consume** | Call first on every session or when the user asks “is the house online?” |
| **Utilize** | Health checks; refuse deep queries if `ha_reachable` is false; explain token misconfig from `detail` |

#### `get_ha_config`
| | |
| --- | --- |
| **Returns** | Sanitized config: units, currency, language, URLs, sample of loaded components |
| **Consume** | When answering about °C/°F, timezone, or which integrations appear loaded |
| **Utilize** | Localize answers (“temps are Celsius”); confirm Assist/energy stack presence without dumping full component list |

#### `list_ha_services` (`domain` optional)
| | |
| --- | --- |
| **Returns** | Catalog of domain → service **names** only |
| **Consume** | “What can Home Assistant do for climate/lights?” documentation questions |
| **Utilize** | Explain capabilities; draft *suggested* UI steps for a human. **Never** execute. `commands_allowed` is always false |

---

### Entities (generic)

#### `list_devices` (`domain` optional)
| | |
| --- | --- |
| **Returns** | Summaries: `entity_id`, state, friendly name, domain |
| **Consume** | Inventory / “what’s in the house?” |
| **Utilize** | Build an overview; pick candidates for `get_entity` |

#### `get_entity` (`entity_id` required)
| | |
| --- | --- |
| **Returns** | One entity with safe attributes (secrets redacted) |
| **Consume** | Precise “what is X doing?” |
| **Utilize** | Cite state + key attributes (temp, battery, fault). Rejects domains outside the allowlist |

#### `get_entities` (`entity_ids` CSV and/or `domain`)
| | |
| --- | --- |
| **Returns** | Batch of entity payloads |
| **Consume** | Compare several devices in one turn |
| **Utilize** | Dashboards-in-prose; multi-room summaries |

#### `search_entities` (`query`, optional `domain`)
| | |
| --- | --- |
| **Returns** | Up to 200 matches by id/name substring |
| **Consume** | User said “heat pump” / “fault” without knowing the entity_id |
| **Utilize** | Resolve natural language → entity_id, then `get_entity` |

---

### By domain (status only)

#### `get_climate` (`entity_id` optional, `*` = all)
| | |
| --- | --- |
| **Returns** | Mode, current/setpoint temps, hvac_action |
| **Consume** | HVAC / comfort questions |
| **Utilize** | Explain heating status for owners or (via BMS narrative) companies — still no setpoint changes |

#### `get_sensors` / `get_binary_sensors`
| | |
| --- | --- |
| **Returns** | All `sensor.*` / `binary_sensor.*` summaries |
| **Consume** | Temps, humidity, faults, door/window, motion |
| **Utilize** | Anomaly explainers (“fault binary is on”); environment briefings |

#### `get_switches` / `get_lights` / `get_covers` / `get_locks`
| | |
| --- | --- |
| **Returns** | On/off or position **state** only |
| **Consume** | “Are the lights on?” / “Is the lock locked?” |
| **Utilize** | Presence/security *status* reports. Cannot toggle, open, or unlock |

#### `get_energy_snapshot`
| | |
| --- | --- |
| **Returns** | Heuristic list of energy/power/gas/water-related sensors |
| **Consume** | Energy / bill / solar questions when those sensors exist |
| **Utilize** | Rough consumption narrative; say when the list is empty |

---

### Structure & people

#### `get_areas`
| | |
| --- | --- |
| **Returns** | Rooms/areas (id, name, aliases) |
| **Consume** | “What rooms are defined?” |
| **Utilize** | Map devices to places in answers; guide takeover naming |

#### `get_devices_registry`
| | |
| --- | --- |
| **Returns** | Device registry: name, manufacturer, model, area |
| **Consume** | Hardware inventory (“what Tuya devices are paired?”) |
| **Utilize** | Support / technician briefs; distinguish device vs entity |

#### `get_people`
| | |
| --- | --- |
| **Returns** | `person.*` home/not_home style states |
| **Consume** | Presence questions |
| **Utilize** | Context for automations *explanations* only — no tracking abuse; no account secrets |

#### `list_config_entries`
| | |
| --- | --- |
| **Returns** | Integration domain + title (+ disabled flag) |
| **Consume** | “Is Tuya Local installed? Is cloud Tuya present?” |
| **Utilize** | Enforce product narrative: prefer `tuya_local`, flag unexpected cloud `tuya` |

---

## OpenClaw wiring

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

```bash
openclaw mcp probe home-box
openclaw mcp tools
```

Allow `bundle-mcp` / sandbox tool policy per OpenClaw docs if tools are filtered.

## Compose

```bash
cd C:\AI\ha
docker compose up -d home-box-mcp
```

```env
BMS_HA_TOKEN=...long-lived-token...
```

## Non-negotiables

- Query / explain only — MCP never calls `/api/services`
- No OEM / Tuya cloud as AI path
- Do not publish `:8100` on the public internet without auth + VPN (later)
- Secrets in entity attributes are redacted when possible
