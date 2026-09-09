# HLK-DIO16 — local Ethernet I/O on Home Box

Integrate the Hi-Link **HLK-DIO16** (16 digital inputs + 16 relay outputs) over the house LAN using its proprietary binary TCP protocol. No MQTT, no vendor cloud, no RS485 required for this path.

## Lab device (verified)

| Field | Value |
| --- | --- |
| IP | `192.168.0.49` |
| TCP port | `8080` |
| MAC | `40:d6:3c:34:31:14` |
| Protocol header | `6A A6` |
| Home Box integration | `hlk_dio16` |

Identification: LAN scan for TCP `8080`, then protocol probe (read DI/DO + toggle DO1). Confirmed by unplug/`ping -t` drop-and-recover on this IP.

## Architecture

```text
Home Assistant (Home Box)
      │
      │ custom_components/hlk_dio16
      ▼
HLK-DIO16 driver (asyncio TCP)
      │
      │ TCP :8080   (header 6A A6)
      ▼
HLK-DIO16
  ├── DI01 … DI16  → binary_sensor
  └── DO01 … DO16  → switch
```

On **Docker Desktop (Windows lab)**, HA cannot route to `192.168.0.x` directly. Traffic is redirected by `lan-router` through the Windows SOCKS5 helper (`tuya/socks5-windows.ps1` on port `1080`). Sold Pi/PC images set `ENABLE_LAN_SOCKS=0`.

## Prerequisites (Windows lab)

1. Device powered and on the house Ethernet LAN (same L2/L3 as the box host).
2. Start SOCKS (after each Windows reboot):

```powershell
powershell -ExecutionPolicy Bypass -File .\tuya\socks5-windows.ps1
```

3. Ensure `lan-router` is up **in the same netns as HA**. After any `homeassistant` recreate/restart:

```bash
docker compose up -d --force-recreate lan-router
```

(`depends_on` alone does not reattach `network_mode: service:homeassistant` children.)

4. Smoke-test from inside HA:

```bash
docker compose exec homeassistant \
  python /config/custom_components/hlk_dio16/smoke.py --host 192.168.0.49
```

Expect: read inputs/outputs, toggle DO01, restore previous state, print `OK`.

## Add in Home Assistant UI

1. Open Home Box → **Settings → Devices & Services → Add Integration**.
2. Search **HLK-DIO16**.
3. Enter:
   - **IP address:** `192.168.0.49` (or the unit’s current DHCP/static IP)
   - **TCP port:** `8080`
4. Submit. Home Box creates one device with:
   - 16× `binary_sensor` — `DI01` … `DI16`
   - 16× `switch` — `DO01` … `DO16`

Example entity IDs on this lab box:

- `binary_sensor.hlk_dio16_192_168_0_49_di01`
- `switch.hlk_dio16_192_168_0_49_do01`

## Commands used (v1)

| Cmd | Role |
| --- | --- |
| `0x07` | Read 16 inputs (2 packed bytes) |
| `0x06` | Read 16 outputs (2 packed bytes) |
| `0x01` | Output control (channel mask + on/off) |

Polling defaults to ~500 ms for both DI and DO while healthy. Connection is persistent TCP with **keepalive**, reconnect backoff capped at **5s**, and a **~20s** last-known-state grace so brief LAN/SOCKS idle drops do not flip entities to unavailable. On failure the client disconnects, backs off, and force-resets the socket every few failures so entities recover when the LAN/SOCKS path returns without a manual reload.

**Windows lab:** keep `tuya\socks5-windows.ps1` running (start after each reboot). If the PC sleeps or the SOCKS process exits, HLK will look lost until SOCKS is back — the integration will self-heal within the grace/backoff window.

## Source layout

```text
image/custom_components/hlk_dio16/
  protocol.py     # frame encode/decode + checksum
  client.py       # TCP connect / read / set_output
  coordinator.py  # HA polling
  config_flow.py  # IP + port setup
  switch.py       # DO01–DO16
  binary_sensor.py# DI01–DI16
  smoke.py        # hardware smoke test
```

Protocol framing was cross-checked against the MIT-licensed [jameshilliard/hlk-dio16](https://github.com/jameshilliard/hlk-dio16) implementation and validated on this physical unit.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Config flow / smoke: timeout from container | SOCKS script running? `lan-router` up? `ENABLE_LAN_SOCKS=1`? |
| Host ping works, HA shows device unavailable | Start `tuya/socks5-windows.ps1` (required after every Windows reboot; keep it running while HA is up). Integration self-heals once SOCKS is back; wait up to ~20s grace / few retries, or reload HLK if stuck |
| Host ping + SOCKS OK, HA still unavailable after HA restart | Orphaned `lan-router` netns — `docker compose up -d --force-recreate lan-router` |
| Host ping works, HA does not | Docker Desktop LAN path — SOCKS required on Windows lab |
| Smoke test fails while integration is loaded | Device allows **one TCP client**; unload/disable the integration first, or trust HA’s connection |
| Wrong device after DHCP change | Re-scan TCP `8080`, update the integration host, or re-add |
| Relays click in smoke but entities unavailable | Reload the integration or restart `homeassistant` |

## Later (not in v1)

- Device-local auto/linkage rules (`0x0F`, `0x10`–`0x1F`) for fail-soft BMS logic
- Configurable poll intervals
- Shared “BMS I/O” abstraction for other Ethernet controllers
