# Upstream Home Assistant org — what we use

Org: [https://github.com/home-assistant](https://github.com/home-assistant) (~106 public repositories).

Our private docs and (later) code stay under **[osokuka](https://github.com/osokuka)**. We do not contribute this product into the upstream org.

## Dependency map for Home Box

| Upstream repo | Stars (approx.) | License | Our use |
| --- | --- | --- | --- |
| [core](https://github.com/home-assistant/core) | ~90k | Apache-2.0 | Runtime engine via container image |
| [docker](https://github.com/home-assistant/docker) / GHCR image | — | Apache-2.0 | Base image `ghcr.io/home-assistant/home-assistant` |
| [frontend](https://github.com/home-assistant/frontend) | ~5.6k | Other / NOASSERTION | Stock UI today; rebrand carefully |
| [brands](https://github.com/home-assistant/brands) | — | — | Integration logos (cache); cosmetic |
| [home-assistant-js-websocket](https://github.com/home-assistant/home-assistant-js-websocket) | ~0.4k | Other | Only if we build a custom web shell |
| [android](https://github.com/home-assistant/android) / [iOS](https://github.com/home-assistant/iOS) | — | — | Optional branded companion later |
| [architecture](https://github.com/home-assistant/architecture) | — | — | Reference only |

## Explicitly out of scope (we are Container-only)

| Repo family | Why we skip it |
| --- | --- |
| supervisor | HassOS/Supervised control plane |
| operating-system (+ blobs/full-images) | Full appliance OS |
| addons / plugin-* | Supervisor add-on ecosystem |
| installer / supervised-installer | Different install paths |
| my.home-assistant.io / Nabu Casa-related sites | Cloud onboarding we disable |

## Custom component (third party, not HA org)

- [make-all/tuya-local](https://github.com/make-all/tuya-local) — **Tuya Local** only; Python deps baked into our image (`tinytuya`).
- Core integration **`tuya`** (`cloud_push`) is **not** used and must not be configured on Home Box.

## Rebrand implications by repo

1. **core** — Keep consuming releases; pin version in Dockerfile; attribute Apache-2.0.
2. **frontend** — Prefer themes + custom panels before any fork; license is not a clean Apache SPDX.
3. **brands** — Do not ship HA wordmarks as our product logo.
4. **websocket / companions** — Defer until Phase 3–4 in [REBRAND.md](REBRAND.md).

## Practical pull list (engineers)

When updating the box:

1. Track HA Core release notes for the pinned image tag.
2. Rebuild `home-box:local` so wheels stay offline at runtime.
3. Retest egress filter (no Core WAN) and ingest agent after upgrades.
4. Retest BMS nginx WebSocket proxy to `/api/websocket`.
