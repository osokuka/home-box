# Integrations — Home Box

## Tuya (first deployment)

| Integration | Source | Allowed? |
| --- | --- | --- |
| **Tuya Local** (`tuya_local`) | Baked into Home Box image (`image/custom_components/tuya_local`) | **Yes — required** |
| **Tuya** (`tuya`) | Home Assistant Core (`cloud_push`) | **No** — vendor cloud |

- Dependency: `tinytuya` installed at image build (`image/requirements.txt`).
- **Add devices:** CSV / Excel → http://127.0.0.1:8098/ or manual Tuya Local — see [TUYA_DEVICE_IMPORT.md](TUYA_DEVICE_IMPORT.md).
- Never add Core **Tuya** / Smart Life cloud login on a Home Box.

Lab LAN path for Docker Desktop: `ENABLE_LAN_SOCKS=1` + `tuya/socks5-windows.ps1`. Sold Pi/PC: `ENABLE_LAN_SOCKS=0`.

## HLK-DIO16 (Ethernet digital I/O)

| Integration | Source | Allowed? |
| --- | --- | --- |
| **HLK-DIO16** (`hlk_dio16`) | Baked into Home Box image (`image/custom_components/hlk_dio16`) | **Yes — local LAN** |

- Protocol: proprietary binary TCP on port **8080** (header `6A A6`). No MQTT, no vendor cloud, no RS485 required.
- Add via **Settings → Devices & Services → Add Integration → HLK-DIO16** (IP + port).
- Creates 16 `binary_sensor` inputs (DI01–DI16) and 16 `switch` outputs (DO01–DO16).
- Full procedure, lab IP, and SOCKS notes: [HLK_DIO16.md](HLK_DIO16.md).

Lab unit (verified): **`192.168.0.49:8080`**.

Smoke test against hardware (from repo root):

```bash
docker compose exec homeassistant \
  python /config/custom_components/hlk_dio16/smoke.py --host 192.168.0.49
```
