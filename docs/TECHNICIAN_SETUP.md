# Technician notes — BMS House Box

You set up **devices on the house box**. You do not assign HVAC companies. You do not create company passwords in HA. The owner does that.

## Privacy

- Open HA at **http://127.0.0.1:8123** on the box, **http://192.168.0.10:8123** on the LAN, or **http://windows-lab.ha.localhost:8080** through BMS nginx (same port as the operator UI). Add `127.0.0.1 windows-lab.ha.localhost` to the Windows hosts file if that name does not resolve. WireGuard comes later.
- Devices: local protocols only (Zigbee, Matter, local Tuya). No Tuya/Smart Life cloud, no Nabu Casa.
- IoT VLAN on the router: **no internet**. This PC/Pi is not their WAN gateway; if the router still NATs them, they will phone home.
- After reboot on this Windows lab, start `tuya\socks5-windows.ps1` so Docker can reach `192.168.0.x`. Sold Pi: `ENABLE_LAN_SOCKS=0`.

## Add devices

1. Owner (or you under the bootstrap login, then hand over) opens HA.
2. Pair locally. For Tuya Wi‑Fi: Tuya Local **manual** IP + device id + local key. Close Smart Life first.
3. Heat pump: use **Heat**, not Cool.

## Company troubleshooting

- **Read-only status** (temps, mode): goes to our platform from this box. Companies do not get on/off from that path.
- **If they need to look at HA:** the **owner** uses the sidebar item **Company access** and creates the person/login. For no on/off, they put that user in the HA `system-read-only` group. We do not do it for them.
- **If they need on/off:** the owner creates a normal (non-admin) HA user and shares that password themselves.

## Platform ping

`.env` has `BMS_PLATFORM_URL` and `BMS_ENROLL_TOKEN`. `docker compose logs platform-agent` should show `ok slug=…` when the operator platform is up. Optional `BMS_HA_TOKEN` = long-lived token from the owner profile, GET-only.
