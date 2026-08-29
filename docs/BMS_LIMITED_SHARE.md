# BMS contract — Home Box limited share (two gates)

Homeowners enable a **limited share** on the box. That alone shares with **nobody**.  
A company sees data only after the homeowner also grants them in **BMS**.

Passwords / device commands are never part of this path.

---

## Non-negotiables

| Rule | Detail |
| --- | --- |
| Two gates | Box `limited_share_enabled` **and** active BMS `ShareGrant` |
| Limited scope | Status telemetry + support activity (faults / unreachable) only |
| No commands | Companies cannot turn devices on/off via this share |
| Box toggle ≠ grant | Enabling on the box does not pick a company |

---

## Gate 1 — Home Box (implemented in home-box)

| Piece | Detail |
| --- | --- |
| UI | Sidebar **Company access** → “Allow limited share to BMS” |
| Storage | `/config/bms_share.json` → `{ "limited_share_enabled": bool, "scope": ["status","support_activity"] }` |
| API | `GET/POST /api/home_box/limited_share` (HA admin session) |
| Agent | Heartbeat includes `limited_share_enabled` + scope |
| Agent | `POST /ingest/status/` **only when** limited share is ON (devices + `support_activity`) |

When limited share is **OFF**, the agent still heartbeats (box online) but does **not** post status/support payloads.

---

## Gate 2 — BMS (implement in home_automation)

### Heartbeat / snapshot

Accept and persist from ingest heartbeat (or equivalent):

```json
{
  "limited_share_enabled": true,
  "limited_share_scope": ["status", "support_activity"],
  "appliance_uid": "…"
}
```

Expose on machine snapshot (optional but useful for owner UI):

```json
"machine": {
  "limited_share_enabled": true
}
```

Default when missing: `false`.

### Company visibility rule

Company status APIs must return household/device data only when **all** are true:

1. Non-revoked `ShareGrant` for that household ↔ company (and domain)
2. Box `limited_share_enabled === true` (latest heartbeat / stored flag)
3. Subscription not fail-closed

If the box turns limited share off, companies lose visibility even if the grant remains (grant can stay for when the owner re-enables).

### Owner grant UX

Homeowner (client portal / BMS owner login — when available):

1. Sees box limited-share state (on/off)
2. Grants / revokes company share for domains (e.g. `hvac`) — existing ShareGrant model
3. Copy: “Companies only get status & support activity, and only while limited share is on on the box.”

Staff may help create companies; **homeowner** owns the grant.

### Status ingest

`POST /ingest/status/` may include:

```json
{
  "devices": [ /* existing shape */ ],
  "support_activity": [
    { "type": "fault_signal", "entity_id": "…", "state": "on", "name": "…" },
    { "type": "device_unreachable", "entity_id": "climate.…", "state": "unavailable", "name": "…" }
  ],
  "limited_share": true
}
```

BMS should ignore or reject status bodies when stored `limited_share_enabled` is false (defense in depth).

---

## Sequence

```text
Owner enables Limited share on Home Box
        │
        ▼
Agent heartbeats limited_share_enabled=true
Agent posts status + support_activity
        │
        ▼
  (still no company can see it)
        │
Owner grants company X in BMS
        │
        ▼
Company X sees limited status/support for granted domains
        │
Owner toggles Limited share OFF on box  ──or──  revokes grant in BMS
        │
        ▼
Company X loses visibility
```

---

## Acceptance checklist (BMS)

- [ ] Persist `limited_share_enabled` from heartbeat
- [ ] Company status requires grant **and** box flag
- [ ] Owner grant/revoke UX copy matches two-gate model
- [ ] No passwords / command APIs on this path
- [ ] Tests: grant alone insufficient; flag alone insufficient; both required

---

## Out of scope (v1)

- Full HA logbook dump  
- Auto-picking a company from the box  
- OEM / Tuya cloud sharing  
- Optional `password_reset_ack`-style ack for share (not required)
