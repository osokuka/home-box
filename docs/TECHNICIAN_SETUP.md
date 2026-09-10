# Technician notes — Home Box

You set up **devices on the house box**. You do not assign HVAC companies. You do not create company passwords in HA. The owner does that.

## Privacy

- Open HA at **http://127.0.0.1:8123** on the box (nginx gateway), **http://192.168.0.10:8123** on the LAN, or **http://windows-lab.ha.localhost:8080** through BMS nginx. Enroll: **http://127.0.0.1:8123/enroll/**. Add `127.0.0.1 windows-lab.ha.localhost` to the Windows hosts file if that name does not resolve.
- Devices: local protocols only (Zigbee, Matter, local Tuya). No Tuya/Smart Life cloud, no Nabu Casa.
- IoT VLAN on the router: **no internet**. This PC/Pi is not their WAN gateway; if the router still NATs them, they will phone home.
- After reboot on this Windows lab, start `tuya\socks5-windows.ps1` so Docker can reach `192.168.0.x`. Sold Pi: `ENABLE_LAN_SOCKS=0`.

## Add devices

1. Owner (or you under the bootstrap login, then hand over) opens Home Box.
2. **Bulk:** CSV or Excel (.xlsx) → http://127.0.0.1:8123/import/ (see [TUYA_DEVICE_IMPORT.md](TUYA_DEVICE_IMPORT.md)).
3. **Or one-by-one:** Add **Tuya Local** (not Core “Tuya”) → **manual** IP + device id + local key.
4. **Digital I/O:** Add **HLK-DIO16** → IP + port `8080` (lab unit `192.168.0.49`). See [HLK_DIO16.md](HLK_DIO16.md).
5. Heat pump: use **Heat**, not Cool.

Do **not** install or sign in to the official Home Assistant **Tuya** integration (cloud). Home Box only supports **Tuya Local**. Sandbox cloud registration is outside this box.

## Company troubleshooting

- **Read-only status** (temps, mode): goes to our platform from this box. Companies do not get on/off from that path.
- **If they need to look at HA:** the **owner** uses the sidebar item **Company access** and creates the person/login. For no on/off, they put that user in the HA `system-read-only` group. We do not do it for them.
- **If they need on/off:** the owner creates a normal (non-admin) HA user and shares that password themselves.

## Platform ping

1. Enroll: open **http://127.0.0.1:8123/enroll/** and paste the operator QR JSON (or set `BMS_ENROLL_TOKEN` / `BMS_APPLIANCE_UID` in `.env`).
2. `docker compose logs platform-agent` should show `ok slug=… uid=…` when the operator platform is up.
3. Optional `BMS_HA_TOKEN` = long-lived token from the owner profile, GET-only.
