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
| Credentials | Never in BMS QR; owner/password set on box; BMS only toggles `allow_password_reset` |
| Limited share | Box toggle = consent only; company grant in BMS is a second gate — [`BMS_LIMITED_SHARE.md`](./BMS_LIMITED_SHARE.md) |

Owner setup + password-reset hook contract (for BMS implementers): [`BMS_OWNER_AND_PASSWORD_HOOK.md`](./BMS_OWNER_AND_PASSWORD_HOOK.md).

## Phase status

### Phase 0 — Naming / legal
- [x] Public name + slug
- [x] DNS keep `*.ha.*` until WireGuard
- [x] NOTICE / Core attribution

### Phase 1 — Surface brand
- [x] Home Box theme (`image/themes/home_box.yaml`) + default on start
- [x] Logo (`/local/home-box-logo.svg`)
- [x] Getting started + Company access panels (product copy)
- [x] Enroll / import UIs titled Home Box (import: “Apply on Home Box”, not HA)
- [x] Overview / sidebar / tab title → **Home Box** (frontend asset patch at image build + `/local/home-box-brand.js`)
- [x] Agent version string `home-box-0.1` (not `ha-lab`)
- [ ] Operator UI wording on BMS (other team / other repo)

### Phase 2 — Identifier sweep (partial)
- [x] Image `home-box:local`
- [x] Containers `home-box-*` (compose service `homeassistant` kept for DNS)
- [x] Panel ids `home-box-getting-started`, `home-box-company-access`
- [ ] CI publish tags (when CI exists)

### Phase 3–4
- Deferred (custom shell / Companion) — optional later

## Still WireGuard-dependent (partial)

- Home Box **accepts** box peer keys from the enroll QR and writes `config/wireguard/wg0.conf` — [WIREGUARD_QR.md](./WIREGUARD_QR.md)
- BMS must embed the box peer in the QR (other team)
- Production hub / phone peers / HTTPS-over-VPN relay still deferred
- Linux/Pi: WireGuard is in the default `docker compose up -d` stack; Windows: import conf into WireGuard app if Docker Desktop WG is flaky
