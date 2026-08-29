# Rebrand plan — Home Box

**Frozen product name:** **Home Box**  
**Slug:** `home-box`  
Engine under the hood remains Home Assistant Core (Apache-2.0 attribution required). Customer-facing surfaces use Home Box, not “Home Assistant” as the product name.

Official upstream org: [github.com/home-assistant](https://github.com/home-assistant) — we **consume** images/APIs; we do **not** push or fork into that org. Our GitHub home is **osokuka**.

## Why rebrand

- Operator platform is BMS-branded (`osokuka/home_automation`).
- Box UI still shows Home Assistant chrome, domains, and default copy.
- Identifiers still mix `BMS_*`, `ha-box`, `homeassistant`, `bms-company-access`.
- Legal/marketing: ship as **Home Box**, with required open-source attribution — not as “Home Assistant” or Nabu Casa.

## Inventory

| Area | Current | Target |
| --- | --- | --- |
| Product name | Mixed / “BMS House Box” | **Home Box** (done in docs + enroll UI) |
| Docker image | `ha-box:local` | `home-box:local` |
| Containers | `homeassistant`, `ha-platform-agent`, `ha-enroll-ui` | Align where safe (`home-box-agent`, …); HA service hostname may stay for less churn |
| Env vars | `BMS_*` | Keep `BMS_*` for platform contract; document HA as engine-only |
| Custom panel | `bms-company-access` | Product copy → Home Box; module id later |
| HA `homeassistant.name` | `Home` | Household / **Home Box** label |
| Frontend theme | Stock HA | Custom theme + logo |
| Docs | Mixed | Owner docs: Home Box; tech notes may say HA for the engine |
| Companion apps | Stock HA | Optional later |
| Hostnames | `*.ha.localhost` | **TBD:** keep `*.ha.` vs `*.home-box.` / `*.box.` |

## Phased plan

### Phase 0 — Naming freeze — **done (name)**

- [x] Public name: **Home Box**
- [x] Short slug: `home-box`
- [ ] DNS pattern for production (`{slug}.ha.` vs `{slug}.home-box.` / `{slug}.box.`)
- [ ] NOTICE / About with Apache-2.0 Core attribution

### Phase 1 — Surface brand (no Core fork)

- Custom lovelace theme + logo in `www/`
- Company access panel copy → Home Box
- Titles / sidebar / enroll UI (enroll UI updated)
- Operator UI: “Home Box” not “Home Assistant client”

### Phase 2 — Identifier sweep

- Image `home-box:local`, compose names, panel module ids
- CI/build tags under `osokuka`
- GitHub repo rename `bms-ha-box` → `home-box` if desired

### Phase 3 — Optional deeper UI

- Custom shell via `home-assistant-js-websocket` if themes are not enough

### Phase 4 — Optional mobile

- Branded Companion only if required; else web / PWA on our hostname

## What we will not do

- Push to the `home-assistant` GitHub org
- Claim official Home Assistant / Nabu Casa branding
- Strip Core license notices
- Fork supervisor / OS / addons — stay on Container

## Success criteria

- Owner-facing UI says **Home Box**, not Home Assistant (except attribution)
- Technicians still know the engine is HA Container
- Artifacts under **osokuka**
