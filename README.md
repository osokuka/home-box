# Home Box

Private documentation and box stack for **Home Box**: a locked-down Home Assistant Container that enrolls with the BMS operator platform and publishes read-only appliance status.

**Product name:** Home Box · **slug:** `home-box`  
Companion platform: [osokuka/home_automation](https://github.com/osokuka/home_automation) (BMS operator console).

## What this is

| Layer | Responsibility |
| --- | --- |
| **Home Box** (this project) | Local device control, privacy egress, enroll + ingest agent |
| **BMS platform** (`home_automation`) | Subscriptions, enroll tokens, company share grants, operator UI |
| **Upstream Home Assistant** | Core runtime we wrap; we do not publish to the `home-assistant` org |

Home Box is **not** the operator console and **not** a company portal. Trades monitor via BMS share grants, not by owning the box.

## Docs index

| Doc | Purpose |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, network, privacy model |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | How the box talks to BMS (ingest contract) |
| [docs/ONBOARDING_LAB.md](docs/ONBOARDING_LAB.md) | Lab enroll UI (:8099) + camera QR + unique ID |
| [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) | Tuya Local only (not Core cloud Tuya) |
| [docs/TUYA_DEVICE_IMPORT.md](docs/TUYA_DEVICE_IMPORT.md) | CSV / Excel import or manual device add |
| [docs/TECHNICIAN_SETUP.md](docs/TECHNICIAN_SETUP.md) | On-site device pairing procedure |
| [docs/OPENCLAW_MCP.md](docs/OPENCLAW_MCP.md) | Read-only MCP for OpenClaw / AI agents |
| [docs/REBRAND.md](docs/REBRAND.md) | Naming freeze + remaining rebrand phases |
| [docs/UPSTREAM_HA.md](docs/UPSTREAM_HA.md) | Which Home Assistant org repos matter |

## Current lab access

- Direct: `http://127.0.0.1:8123` or LAN `http://192.168.0.10:8123`
- Via BMS nginx: `http://windows-lab.ha.localhost:8080` (hosts entry required)
- Enroll UI: `http://127.0.0.1:8099/`
- WireGuard and production `{slug}.…` hostnames come later

## Status

- Lab stack: HA Core + agent + enroll (:8099) + Tuya import (:8098) + MCP (:8100) + privacy LAN router
- Product name: **Home Box** — see `NOTICE` and [docs/REBRAND.md](docs/REBRAND.md)
- Tuya: **Local only** via CSV/manual — [docs/TUYA_DEVICE_IMPORT.md](docs/TUYA_DEVICE_IMPORT.md)
- AI agents: read-only MCP for OpenClaw — [docs/OPENCLAW_MCP.md](docs/OPENCLAW_MCP.md) (BYO LLM stays in the agent)
- WireGuard / production relay: **not in this pass**
