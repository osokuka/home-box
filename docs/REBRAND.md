# Rebrand plan — Home Box

**Frozen product name:** **Home Box**  
**Slug:** `home-box`  
Engine under the hood remains Home Assistant Core (Apache-2.0 — see `NOTICE`).

## Decisions locked (no WireGuard required)

| Decision | Value |
| --- | --- |
| Product name | Home Box |
| Slug | `home-box` |
| DNS (until VPN exists) | Keep `{slug}.ha.<domain>` / lab `*.ha.localhost` |
| Tuya | **Tuya Local only** — never Core cloud `tuya` |
| Attribution | `NOTICE` at repo root |

## Phase status

### Phase 0 — Naming / legal
- [x] Public name + slug
- [x] DNS keep `*.ha.*` until WireGuard
- [x] NOTICE / Core attribution

### Phase 1 — Surface brand
- [x] Home Box theme (`image/themes/home_box.yaml`) + default on start
- [x] Logo (`/local/home-box-logo.svg`)
- [x] Getting started + Company access panels (product copy)
- [x] Enroll / import UIs titled Home Box
- [ ] Operator UI wording on BMS (other repo)

### Phase 2 — Identifier sweep (partial)
- [x] Image `home-box:local`
- [x] Containers `home-box-*` (compose service `homeassistant` kept for DNS)
- [x] Panel ids `home-box-getting-started`, `home-box-company-access`
- [ ] CI publish tags (when CI exists)

### Phase 3–4
- Deferred (custom shell / Companion) — optional later

## Still WireGuard-dependent (out of this pass)

- Box VPN client, production relay, phone-away path, full edge HTTPS-over-VPN story
