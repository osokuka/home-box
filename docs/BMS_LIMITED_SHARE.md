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
| Agent | `POST /ingest/status/` on **share allowlist change** (full updated list, including off) and when share ON + feed positive |

### `bms_share.json` shape

`sensors`: `[{ "entity_id": "binary_sensor.…", "system": "<client label>" }]`  
`categories`: `[ "hvac", "security", "kitchen", … ]` — labels managed in Company access UI  
`system` is chosen **per sensor by the client** — domain or location.  
Home Box never invents or validates against a fixed list; it only slugs for transport.  
`sensor_entities` remains a derived id list for older readers.

---

## Gate 2 — BMS

Same two-gate visibility as before.  
Status ingest includes each device’s client `system` string as-is (plus `telemetry.sensor.classification`).  
**BMS must accept free-form `system` values** (domain or location), not only a fixed enum — otherwise location labels and custom names return HTTP 400 (`Unknown system`).

Heat-pump rows still use `class: "heat_pump"` with `system: "hvac"` (HA climate domain).

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
- [ ] Accept `binary_input` devices with **free-form** `system` (domain or location)
- [ ] Company status requires grant **and** box flag
- [ ] No passwords / command APIs on this path
