# BMS contract — Home Box sensory share (two gates)

Homeowners enable a **sensory share** on the box and pick which **binary sensors** may leave.  
That alone shares with **nobody**. A company sees data only after the homeowner also grants them in **BMS**.

The Docker **sensory-feed** agent (`platform-agent` / `home-box-agent`) checks the feed every few seconds and **posts only when the feed is positive**. Idle/empty feeds are not pushed. Relays/switches are never included.

Passwords / device commands are never part of this path.

---

## Non-negotiables

| Rule | Detail |
| --- | --- |
| Two gates | Box `limited_share_enabled` **and** active BMS `ShareGrant` |
| Sensory only | Selected `binary_sensor.*` + HVAC status telemetry — **never** `switch.*` / DO |
| Idle = no POST | Empty or inactive feed → heartbeat only, no `/ingest/status/` |
| Positive = POST | Active binary sensor (`on`) and/or HVAC mode not `off`/`unknown` |
| No commands | Companies cannot turn devices on/off via this share |
| Box toggle ≠ grant | Enabling on the box does not pick a company |

---

## Gate 1 — Home Box

| Piece | Detail |
| --- | --- |
| UI | Sidebar **Company access** → “Allow sensory share to BMS” + sensor checkboxes |
| Storage | `/config/bms_share.json` |
| API | `GET/POST /api/home_box/limited_share` |
| Agent | Heartbeat ~20s; feed check every **5s** (env `BMS_INTERVAL`) |
| Agent | `POST /ingest/status/` only when share ON **and** `feed_is_positive` |

### `bms_share.json` shape

```json
{
  "v": 1,
  "limited_share_enabled": true,
  "scope": ["status", "support_activity", "sensors"],
  "sensor_entities": [
    "binary_sensor.hlk_dio16_192_168_0_49_di01"
  ],
  "updated_at": "…"
}
```

`sensor_entities` must be `binary_sensor.*` only; other domains are dropped.

---

## Gate 2 — BMS

Same two-gate visibility as before. Domain grants may include `hvac`, `security`, etc.  
Status ingest may include devices with `system: "security"` (`class: "binary_input"`) and `system: "hvac"` (`class: "heat_pump"`).

Optional body field: `"feed": "sensory"`.

---

## Sequence

```text
Owner enables sensory share + selects HLK DI sensors on Home Box
        │
        ▼
Agent heartbeats limited_share_enabled=true
Agent polls feed every 5s
        │
   feed idle ──▶ no status POST
   feed positive ──▶ POST /ingest/status/
        │
  (still no company can see it)
        │
Owner grants company in BMS (e.g. security domain)
        │
        ▼
Company sees allowed sensory devices for granted domains
```

---

## Acceptance checklist (BMS)

- [ ] Persist `limited_share_enabled` from heartbeat
- [ ] Accept `binary_input` / `security` devices
- [ ] Company status requires grant **and** box flag
- [ ] No passwords / command APIs on this path
