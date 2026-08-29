# BMS contract — Home Box owner setup & password-reset hook

This document is the **implementation contract** for the BMS (`home_automation`) side.  
Home Box never receives passwords from BMS. Passwords are chosen and shown **only on the box**.

Related Home Box UI: enroll service `:8099` (after QR + successful BMS hello).

---

## Non-negotiables

| Rule | Detail |
| --- | --- |
| No passwords in QR | Enroll QR stays `{v, unique_id, enroll_token, ha_hostname}` (+ optional platform URL). **Never** `password`, `username`, or hashed credentials. |
| No passwords in snapshot | Ingest subscription/heartbeat payloads must **never** include user passwords. |
| BMS switch = enablement only | Staff toggles whether the **box may show** local password UI. |
| User sees password on box | Household enters / confirms the new password on Home Box (`:8099`). BMS operators do not see it. |

---

## Feature A — Post-QR owner setup (box-local)

**Flow (box):**

1. Technician/owner scans BMS QR on `http://<box>:8099/`.
2. Box saves enroll file and **verifies BMS hello** (`GET /api/v1/ingest/subscription/` with enroll bearer).
3. On success, box shows **Home Box admin / owner setup** (name, username, password, confirm).
4. Box creates the HA owner **locally** (HA onboarding or Home Box admin API).
5. Staff later marks handover `taken_over` on BMS (existing UX).

**BMS work for Feature A:** none beyond existing enroll + snapshot. Do not put credentials in prepare-box / QR.

---

## Feature B — Password-reset enable switch (BMS ↔ box)

### 1. Data model (BMS)

Add a boolean on **`Deployment`** (per machine / sold box), default **`false`**:

| Field | Type | Default | Meaning |
| --- | --- | --- | --- |
| `allow_password_reset` | `BooleanField` | `false` | When `true`, Home Box may show “set / reset Home Box password” UI |

Suggested Django:

```python
allow_password_reset = models.BooleanField(
    default=False,
    help_text="When on, the Home Box may show local password reset UI. Never stores the password.",
)
```

Migration + admin/API exposure on the machine card.

### 2. Operator UI (BMS)

On the client / machine card (next to handover controls):

- Toggle / switch: **Allow Home Box password reset**
- Help text: *Turns on password setup on the box only. You will not see the new password here.*
- Optional: button **Turn off** after support call

Staff workflow:

1. Owner locked out → staff sets switch **ON**.
2. Owner opens Home Box enroll UI (`:8099`) → resets password locally → sees/confirm password there.
3. Staff sets switch **OFF** (manual v1), or box notifies completion (optional below).

### 3. Subscription snapshot (required)

Extend **`subscription_snapshot()`** so both:

- `GET /api/v1/ingest/subscription/`
- `POST /api/v1/ingest/heartbeat/` (same snapshot shape)

include:

```json
{
  "machine": {
    "id": 123,
    "name": "…",
    "site_slug": "…",
    "ha_hostname": "…",
    "hardware_kind": "…",
    "tunnel_type": "…",
    "handover_state": "awaiting_takeover",
    "allow_password_reset": false
  }
}
```

| Key | Type | Required | Notes |
| --- | --- | --- | --- |
| `machine.allow_password_reset` | boolean | **yes** (once shipped) | Missing → Home Box treats as `false` |

Update `working_scope/architecture/API_CONTRACTS.md` accordingly.

### 4. Staff PATCH (required)

Allow operators to flip the flag without a full deployment rewrite, e.g. existing machine PATCH:

```http
PATCH /api/v1/…/deployments/<id>/
Authorization: (staff session)
Content-Type: application/json

{ "allow_password_reset": true }
```

(Use your existing deployment PATCH path; include field in serializer `read/write` for admin/operator roles only.)

### 5. Optional — box acknowledges reset (v1.1)

Home Box **may** later POST (no password in body):

```http
POST /api/v1/ingest/password_reset_ack/
Authorization: Bearer <enroll_token>
Content-Type: application/json

{
  "appliance_uid": "<uuid>",
  "ok": true,
  "at": "2026-08-29T12:00:00+00:00"
}
```

BMS behaviour if implemented:

- Verify enroll token + uid match.
- Set `allow_password_reset=false` on that deployment.
- Do **not** log or accept a password field (reject if present).

**v1 can skip this** — staff clears the switch manually.

---

## What Home Box does with the flag

| `allow_password_reset` | Box behaviour |
| --- | --- |
| `false` / missing | Hide password-reset step (owner setup after **first** successful QR hello still allowed when no owner / first-run). |
| `true` | Show reset UI on `:8099`; user sets new password locally; success copy stays on box. |

Agent persists a local cache (e.g. `/config/bms_runtime.json`) from each snapshot for the enroll UI / HA helper — still **no secrets** from BMS.

---

## Sequence diagrams

### First enroll + owner credentials

```text
BMS prepare-box QR ──scan──► Home Box :8099
                              │ save bms_enroll.json
                              │ GET /ingest/subscription/  (hello)
                              ▼
                         hello OK → owner form (name/user/pass)
                              │ create HA owner locally
                              ▼
                         owner can open :8123
BMS staff ──(later)──► Mark taken_over
```

### Support password reset

```text
Staff: allow_password_reset = true
   │
   ▼
Heartbeat/subscription snapshot → box
   │
   ▼
Owner opens :8099 → Reset password form
   │ password never leaves the box toward BMS
   ▼
Staff: allow_password_reset = false
   (or optional password_reset_ack)
```

---

## Acceptance checklist (BMS)

- [ ] `Deployment.allow_password_reset` default `false`
- [ ] Operator UI switch on machine card
- [ ] Snapshot + heartbeat include `machine.allow_password_reset`
- [ ] Staff PATCH can toggle the flag
- [ ] QR / prepare-box / enroll mint paths unchanged (no credential fields)
- [ ] API contract doc updated
- [ ] Tests: snapshot false by default; true after PATCH; enroll token cannot set the flag

---

## Out of scope for this hook

- Minting or displaying HA passwords in BMS UI  
- Emailing passwords from BMS  
- Changing BMS operator `admin` login  
- WireGuard / remote `:8099` exposure (still lab/LAN; WAN needs VPN later)
