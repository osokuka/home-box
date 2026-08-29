# Integration — House box ↔ BMS platform

This stack is the **house**. WireGuard is **not** in this pass. HA is a normal HTTP service next to BMS.

## How it is reached (now)

- HA listens on host **TCP 8123** (all interfaces), same idea as BMS on **8080**.
- BMS nginx also serves the household hostname:
  - Operator UI: `http://localhost:8080`
  - This house: `http://windows-lab.ha.localhost:8080` → this HA (WebSocket upgraded)
  - Lab stub: `http://lab.ha.localhost:8080` (fake HA in the operator compose)
- Set `ha_external_url` / `ha_internal_url` in `config/secrets.yaml` (from `image/secrets.example.yaml`).
- Reverse proxy must upgrade `/api/websocket`. HA 2026 stores HTTP settings in `.storage/http` after first boot (yaml `http:` is migrated once). New boxes pick up `trusted_proxies` from `image/configuration.yaml` on that first start.

Later: `{slug}.ha.{domain}` over WireGuard. Do not build that here yet.

## Ingest API (platform-agent)

Sidecar talks only to the operator repo APIs:

| Method | Path | Why |
| --- | --- | --- |
| GET | `/api/v1/ingest/subscription/` | Plan, slug, fail-closed |
| POST | `/api/v1/ingest/heartbeat/` | Box alive + service statuses |
| POST | `/api/v1/ingest/status/` | **Read-only** device snapshot (mode, temps). No commands |

### Auth and env

| Variable | Meaning |
| --- | --- |
| `BMS_PLATFORM_URL` | Operator base URL (lab: `http://host.docker.internal:8080`) |
| Enroll file `/config/bms_enroll.json` | From enroll UI (:8099); preferred token + `unique_id` |
| `BMS_ENROLL_TOKEN` | Env fallback if no enroll file |
| `BMS_APPLIANCE_UID` | Env fallback unique ID (must match token) |
| `BMS_HA_URL` | In-compose HA URL (`http://homeassistant:8123`) |
| `BMS_HA_TOKEN` | Optional long-lived HA token for agent status / MCP |
| `BMS_INTERVAL` | Poll seconds (default 20) |
| `BMS_CLIMATE_ENTITY` | Optional climate hint for agent status mapping |

Owner credentials and password reset are **not** env vars. See [`BMS_OWNER_AND_PASSWORD_HOOK.md`](./BMS_OWNER_AND_PASSWORD_HOOK.md): QR has no passwords; BMS exposes `machine.allow_password_reset`; box UI on `:8099`.

Lab enroll: see [ONBOARDING_LAB.md](ONBOARDING_LAB.md). Heartbeat includes `appliance_uid` when known.

The agent never calls `/api/services`.

### Payload shape

- Uses BMS names (`heat_pump`, `hvac.temperature`, `hvac.mode`, …).
- No raw `entity_id` is sent to the platform.
- Climate mapping prefers live `/api/states`; falls back to `.storage/core.restore_state`.

### Fail-closed

If subscription reports `fail_closed`, the agent still heartbeats but should not treat the box as fully live for status sharing (platform decides).

## Privacy (still true)

- HA Core egress is RFC1918 / link-local / multicast only. No Nabu Casa, Tuya cloud, GitHub, PyPI, or analytics from Core.
- Python deps for custom components are baked into `home-box:local` at image build.
- IoT gadgets must not use the house WAN (router VLAN with no default route).
- Lovelace is not iframed into other sites (`use_x_frame_options: true`).
- `image/configuration.yaml` does **not** load `default_config`.

## Company people

| Need | Who creates it | What they can do |
| --- | --- | --- |
| Watch status / troubleshoot without buttons | Platform share (operator repo) | Requires box **Limited share** ON **and** BMS company grant — [`BMS_LIMITED_SHARE.md`](./BMS_LIMITED_SHARE.md) |
| Open HA and look around | **House owner** in HA → People | Owner chooses user vs read-only group |
| Turn devices on/off | **House owner** gives a normal HA user | Not BMS staff |

Sidebar **Company access** (admin) is the owner checklist. We do not mint those passwords.

Lab: Docker Desktop cannot route LAN, so `ENABLE_LAN_SOCKS=1` + `tuya/socks5-windows.ps1`. Sold Pi/PC: `ENABLE_LAN_SOCKS=0`.

## Planned integration steps (platform side)

1. Deployment exists with enroll token (operator already supports this).
2. Box `.env` points at platform URL + token; agent shows `ok slug=…`.
3. Owner/share grants expose heat-pump (or other) status to HVAC company in operator UI.
4. Later: WireGuard hostname, production TLS, rotate enroll tokens, multi-device classes beyond climate.

## Local start (runtime tree, not this docs repo)

```bash
cd C:\AI\ha
docker compose build
docker compose up -d
```

- Direct: http://192.168.0.10:8123 (or http://127.0.0.1:8123)
- Via BMS nginx: `http://windows-lab.ha.localhost:8080`
