# BMS House Box

Private documentation for the **client house box**: a locked-down Home Assistant Container stack that enrolls with the BMS operator platform and publishes read-only appliance status.

This repository contains **documentation only**. Runtime code lives locally under `C:\AI\ha` and is not pushed here yet.

Companion platform repo: [osokuka/home_automation](https://github.com/osokuka/home_automation) (BMS operator console).

## What this is

| Layer | Responsibility |
| --- | --- |
| **House box** (this project) | Local device control, privacy egress, ingest agent |
| **BMS platform** (`home_automation`) | Subscriptions, enroll tokens, company share grants, operator UI |
| **Upstream Home Assistant** | Core runtime we wrap; we do not publish to the `home-assistant` org |

The house box is **not** the operator console and **not** a company portal. HVAC and other trades monitor via BMS share grants, not by owning the box.

## Docs index

| Doc | Purpose |
| --- | --- |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Components, network, privacy model |
| [docs/INTEGRATION.md](docs/INTEGRATION.md) | How the box talks to BMS (ingest contract) |
| [docs/TECHNICIAN_SETUP.md](docs/TECHNICIAN_SETUP.md) | On-site device pairing procedure |
| [docs/REBRAND.md](docs/REBRAND.md) | Product rebrand inventory and phases |
| [docs/UPSTREAM_HA.md](docs/UPSTREAM_HA.md) | Which Home Assistant org repos matter |

## Current lab access

- Direct HA: `http://127.0.0.1:8123` or LAN `http://192.168.0.10:8123`
- Via BMS nginx: `http://windows-lab.ha.localhost:8080` (hosts entry required)
- WireGuard and `{slug}.ha.{domain}` come later

## Status

- Lab stack: Docker Compose on Windows (HA Core + platform-agent + LAN privacy router)
- Ingest: subscription / heartbeat / read-only device status
- Rebrand: planned; Core stays under the hood (see REBRAND.md)
