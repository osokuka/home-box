# Architecture — Home Box

## Roles

```
┌─────────────────────────────┐         ┌──────────────────────────────┐
│  House box (this project)   │  ingest │  BMS platform                 │
│  HA Core :8123              │────────▶│  osokuka/home_automation     │
│  platform-agent (read-only) │  HTTP   │  Operator UI :8080           │
│  privacy egress (iptables)  │         │  Companies via ShareGrant    │
└──────────────┬──────────────┘         └──────────────────────────────┘
               │ local protocols only
               ▼
        IoT VLAN (no WAN) — Tuya local, HLK-DIO16 Ethernet I/O, Zigbee, Matter, …
```

- **House owner** controls devices and creates any HA logins for technicians.
- **BMS staff / companies** see telemetry through the platform. They do not get on/off via ingest.
- **Technician** pairs devices on the box; does not assign HVAC companies or mint company passwords in HA.

## Compose services (local stack)

| Service | Image / build | Job |
| --- | --- | --- |
| `homeassistant` | `home-box:local` from `image/Dockerfile` | HA Core + baked Python deps (internal :8123) |
| `gateway` | `nginx:1.27-alpine` | **Sole host port** (`8123`) → path-routes to HA / enroll / import / MCP |
| `platform-agent` | `python:3.12-alpine` + `platform/agent.py` | Enroll, heartbeat, **sensory feed** status POST |
| `lan-router` | shares HA netns | Privacy iptables; optional SOCKS for Docker Desktop lab |

## Image strategy

- Base: `ghcr.io/home-assistant/home-assistant` (stable / pinned version).
- Custom components’ Python deps (e.g. `tinytuya`) are installed **at image build**.
- Runtime Core is blocked from PyPI, GitHub, Nabu Casa, vendor clouds (see privacy).

## Configuration layout (local tree)

```
ha/
  compose.yaml
  image/           # Dockerfile, configuration.yaml, packages, www panel
  platform/        # ingest agent
  network/         # protect-egress.sh
  tuya/            # lab SOCKS helpers
  config/          # runtime (secrets, DB, .storage) — not for public git
```

`image/configuration.yaml` is mounted read-only over `/config/configuration.yaml`. It does **not** load `default_config` (avoids cloud/my/alerts bundles). Packages under `image/packages/` tighten logging.

## Privacy model

1. **HA Core egress** — OUTPUT filtered to RFC1918 / link-local / multicast / Docker DNS only.
2. **IoT devices** — router VLAN with **no default route**. This compose cannot stop gadget firmware if the router still NATs them.
3. **No iframe of Lovelace** into other sites (`use_x_frame_options: true`).
4. **Agent** — GET HA states only when `BMS_HA_TOKEN` is set; never POST `/api/services`.

## Reachability (now vs later)

| Phase | How clients open HA |
| --- | --- |
| **Now** | Host TCP **8123 only** (nginx gateway); BMS nginx may still proxy `{slug}.ha.localhost:8080`; WireGuard edge `{slug}.scardustech.com` via overlay `:8123` |
| **Later** | Hardened production TLS / relay policies as needed |

Trusted proxies in HA HTTP config cover Docker/BMS nginx ranges only (not `0.0.0.0/0`).

## Company access path

1. Day-to-day: BMS share grant → read-only status from ingest payloads.
2. Deep troubleshooting in HA UI: **owner** creates a person via sidebar **Company access** checklist.
3. View-only HA user: `system-read-only` group (manual / future helper). BMS never sets that password.
