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
