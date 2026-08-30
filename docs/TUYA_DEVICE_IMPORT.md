# Tuya devices on Home Box — CSV, Excel, or manual

Home Box uses **Tuya Local only**. It never uses Tuya / Smart Life cloud.

Your **sandbox** (elsewhere) produces device credentials. Home Box only **imports** them.

## Two ways to add devices

| Method | When |
| --- | --- |
| **CSV / Excel (.xlsx)** | Many devices at once. Upload on Home Box `:8098` |
| **Manual** | One device: Settings → Devices → Add integration → **Tuya Local** → **manual** |

Legacy `.xls` is not supported — use `.xlsx` or CSV UTF-8.

## Columns

| Column | Required | Notes |
| --- | --- | --- |
| `name` | yes | Display title in Home Box |
| `device_id` | yes | Tuya device id |
| `local_key` | yes | Local key from sandbox export |
| `host` | yes | Device LAN IP on the **house** network |
| `protocol_version` | no | e.g. `3.4` or `auto` (default `auto`) |
| `type` | no* | Tuya Local profile id (e.g. `wifi_heatpump`). Needed for auto-apply |
| `poll_only` | no | `true` / `false` (default `false`) |

\*Without `type`, use the file as a checklist and finish each device manually in Tuya Local (it will offer matching profiles).

Excel: put these headers on the **first sheet**, row 1.  
CSV template: [templates/tuya_devices.csv](templates/tuya_devices.csv)

## Bulk import UI

1. Place devices on the house LAN (same network Home Box can reach).
2. Open **http://127.0.0.1:8098/** on the box.
3. Upload **CSV** or **Excel (.xlsx)**, or paste CSV text.
4. Review the list (Excel is converted to CSV in the text box).
5. **Save inventory** — stores a queue on the box (`/config/tuya_import_queue.json`, not committed).
6. Either:
   - **Apply on Home Box** (needs a long-lived access token in `BMS_HA_TOKEN`, devices online, and `type` set), or  
   - **Manual** — for each row, Add **Tuya Local** → manual, copy fields from the import page.

## Manual one-by-one

1. Settings → Devices & services → Add integration → **Tuya Local**.
2. Choose **manual** (not cloud).
3. Enter device id, IP, local key, protocol.
4. Pick the device profile / name.
5. Confirm entities.

## Rules

- Do **not** add Core integration **Tuya** (cloud).
- Do **not** put sandbox cloud API keys on Home Box.
- After import, devices talk **LAN only** to Home Box.
- Keep CSV / Excel files with keys offline / encrypted; treat like passwords.
