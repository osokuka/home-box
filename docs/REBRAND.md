# Rebrand plan — BMS House Box

Working product name in these docs: **BMS House Box** (under-the-hood engine remains Home Assistant Core). Customer-facing surfaces should stop looking like stock Home Assistant over time.

Official upstream org: [github.com/home-assistant](https://github.com/home-assistant) — we **consume** images/APIs; we do **not** push or fork into that org. Our GitHub home is **osokuka**.

## Why rebrand

- Operator platform is already BMS-branded (`osokuka/home_automation`).
- House UI still shows Home Assistant chrome, domains, and default copy.
- Identifiers mix `BMS_*`, `ha-box`, `homeassistant`, `bms-company-access`.
- Legal/marketing: ship as our product, with required open-source attribution — not as “Home Assistant” or Nabu Casa.

## Inventory (what still says Home Assistant / HA / BMS inconsistently)

| Area | Current | Rebrand action |
| --- | --- | --- |
| Product name | Informal “HA box” / Home Assistant | Lock **BMS House Box** (or final trademark) everywhere customer-facing |
| Docker image | `ha-box:local` | Rename when publishing (e.g. `bms-house-box`) |
| Containers | `homeassistant`, `ha-platform-agent` | Align names with product |
| Env vars | `BMS_*`, `BMS_HA_*` | Keep BMS prefix for platform; document HA as engine-only |
| Custom panel | `bms-company-access`, “Company access” | Keep BMS; replace “Home Assistant” strings with product name |
| HA `homeassistant.name` | `Home` | Set to household / product label |
| Frontend theme | Stock HA | Custom theme + logo (no Core fork required) |
| Docs / tech notes | Speak “HA” freely | Technician docs may keep “HA” as engine nickname; owner docs use product name |
| Companion apps | Stock HA apps | Optional later; only if we need branded mobile |
| Hostnames | `*.ha.localhost`, later `*.ha.{domain}` | Decide whether `ha` stays in DNS or becomes `box` / brand slug |

## Phased plan

### Phase 0 — Naming freeze (docs / product)

- Confirm public name and short slug (`bms-house-box`).
- Decide DNS pattern for production (`{slug}.ha.` vs `{slug}.box.`).
- Keep Apache-2.0 attribution for Core in NOTICE / About.

### Phase 1 — Surface brand (no Core fork)

- Custom lovelace theme + logo in `www/`.
- Rewrite Company access panel copy to product name.
- Set `external_url` / titles / sidebar labels.
- Operator UI copy: “House box” not “Home Assistant client” where customers see it.

### Phase 2 — Identifier sweep (code, when code is published)

- Rename image, compose service aliases (keep internal HA hostname if needed for less churn).
- Align panel module ids (`bms-company-access` → product slug).
- CI/build tags under `osokuka`, never `home-assistant`.

### Phase 3 — Optional deeper UI

- Thin custom shell or partial frontend overlay using `home-assistant-js-websocket`.
- Full **frontend** fork only if Phase 1 is insufficient — license is `NOASSERTION`; legal review first.

### Phase 4 — Optional mobile

- Fork/re-skin Companion (**android** / **iOS**) only if stock HA app branding is unacceptable.
- Otherwise document “use web UI / PWA” under our hostname.

## What we will not do

- Push to or request membership in the `home-assistant` GitHub org.
- Claim official Home Assistant / Nabu Casa partnership without a real agreement.
- Strip required license notices from Core.
- Rebrand by forking **supervisor / operating-system / addons** — we stay on Container.

## Success criteria

- Owner and company UIs say **BMS** (or final brand), not Home Assistant, except an About/attribution line.
- Technicians still know the engine is HA Container for pairing skills.
- All GitHub artifacts live under **osokuka**.
