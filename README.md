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
| [docs/TECHNICIAN_SETUP.md](docs/TECHNICIAN_SETUP.md) | On-site device pairing procedure |
| [docs/REBRAND.md](docs/REBRAND.md) | Naming freeze + remaining rebrand phases |
| [docs/UPSTREAM_HA.md](docs/UPSTREAM_HA.md) | Which Home Assistant org repos matter |

## Current lab access

- Direct: `http://127.0.0.1:8123` or LAN `http://192.168.0.10:8123`
- Via BMS nginx: `http://windows-lab.ha.localhost:8080` (hosts entry required)
- Enroll UI: `http://127.0.0.1:8099/`
- WireGuard and production `{slug}.…` hostnames come later

## Status

- Lab stack: Docker Compose (HA Core + platform-agent + enroll-ui + LAN privacy router)
- Ingest: subscription / heartbeat / read-only device status
- Product name frozen: **Home Box** (`home-box`) — see REBRAND.md for remaining work
