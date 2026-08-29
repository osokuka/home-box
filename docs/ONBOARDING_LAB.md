# Lab onboarding — enroll Home Box with BMS

Operator platform owns prepare-box / QR / handover UI (other repo/location).  
**Home Box** stores the QR on the device and announces with `appliance_uid`.

QR JSON shape (from operator `prepare-box` / enrollment QR):

```json
{"v":1,"unique_id":"<uuid>","enroll_token":"bms_…","ha_hostname":"<slug>.ha.localhost"}
```

## Flow

```text
1. Staff: Prepare box for client on BMS → show enrollment QR
2. Box:   Open http://127.0.0.1:8099/ → Start camera → scan QR
          (or paste JSON / fields if no camera)
3. Box:   platform-agent writes heartbeats with appliance_uid
4. BMS:   waiting_for_device clears; handover → awaiting_takeover
5. Staff: Walk owner through HA takeover (operator checklist — not in this repo)
```

## Services

| Service | Port | Role |
| --- | --- | --- |
| `enroll-ui` | **8099** | Camera QR scan / paste → `/config/bms_enroll.json` |
| `platform-agent` | — | Re-reads enroll each poll; `GET subscription`, `POST heartbeat` (+ uid), `POST status` |
| `homeassistant` | 8123 | HA Core |

Camera frames stay in the browser; only decoded enroll JSON is POSTed to the local enroll API. The jsQR decoder is vendored under `platform/static/` (no CDN at runtime).

Enroll file wins over `.env` for token and unique ID. Optional env fallbacks: `BMS_ENROLL_TOKEN`, `BMS_APPLIANCE_UID`, `BMS_PLATFORM_URL`.

## Start / recreate

```bash
cd C:\AI\ha
docker compose up -d enroll-ui platform-agent
```

- Enroll UI: http://127.0.0.1:8099/
- Clear enroll: DELETE via the Clear button (falls back to env if set)

## Verify

```bash
docker compose logs -f platform-agent
```

Expect lines like `ok slug=… uid=<uuid> live=…`. HTTP 400 `mismatch` means the token and unique ID do not belong together — re-paste the QR from BMS.

## Privacy

Same as the rest of the box: Core stays on private nets; enroll UI only talks to the operator URL you save; no vendor clouds.
