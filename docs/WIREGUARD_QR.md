# WireGuard in the enroll QR — Home Box contract

Home Box accepts an optional **`wireguard`** object in the **same** BMS prepare-box QR used for enroll.

BMS already mints peers at prepare-box; today the QR is enroll-only (`v:1`). Home Box is ready for **`v:2`** with the box peer embedded. **BMS must put the box peer into `qr_payload`** (other team).

## QR shape Home Box accepts

Minimum enroll (unchanged):

```json
{
  "v": 1,
  "unique_id": "<uuid>",
  "enroll_token": "bms_…",
  "ha_hostname": "slug.ha.example"
}
```

With WireGuard (preferred):

```json
{
  "v": 2,
  "unique_id": "<uuid>",
  "enroll_token": "bms_…",
  "ha_hostname": "box-slug.scardustech.com",
  "platform_url": "http://10.10.0.1",
  "wireguard": {
    "role": "box",
    "config": "[Interface]\nPrivateKey = …\nAddress = 10.10.x.y/32\n\n[Peer]\nPublicKey = …\nEndpoint = PUBLIC.IP:51820\nAllowedIPs = 10.10.0.0/16\nPersistentKeepalive = 25\n"
  },
  "admin": {
    "name": "Owner",
    "username": "admin",
    "password": "min-8-chars"
  }
}
```

Optional **`admin`** (or `owner`) is one-time bootstrap: Home Box creates the local admin after BMS hello, then deletes the bootstrap secret. Password is never returned by `/api/status`. If `admin` is omitted, the LAN UI still shows the password form.

### Alternatives Home Box also accepts

**Structured fields** (no full `config` string):

```json
"wireguard": {
  "role": "box",
  "private_key": "…",
  "address": "10.10.x.y/32",
  "server_public_key": "…",
  "endpoint": "PUBLIC.IP:51820",
  "allowed_ips": "10.10.0.0/16",
  "persistent_keepalive": 25
}
```

**Prepare-box style** (paste full prepare response / nested peers):

```json
"wireguard": {
  "endpoint": "PUBLIC.IP:51820",
  "allowed_ips": "10.10.0.0/16",
  "server_public_key": "…",
  "peers": [
    {
      "role": "box",
      "label": "HA box",
      "address": "10.10.x.y/32",
      "private_key": "…",
      "config": "[Interface]…"
    }
  ]
}
```

Home Box picks the peer with `role` in `box|ha|home_box|appliance`, or label containing `box`.

Phone / user peers stay **out of the box QR** (download separately for phones).

## What Home Box does

1. On enroll save → write `/config/wireguard/wg0.conf` (+ `wg_confs/wg0.conf` for linuxserver)
2. If QR included WG → enroll UI calls `/api/wg/apply` (restart `home-box-wireguard` when possible)
3. Webpage shows a **45s countdown** while polling BMS hello
4. When BMS is reachable → reveal **Home Box admin registration** (new password, local only)
5. Status on `:8099` shows WireGuard **saved** + endpoint/address crumbs
6. Clear enroll also clears the WG conf

**Important:** QR `platform_url` (e.g. `http://10.10.0.1`) is saved as-is and used for hello. Lab env `BMS_PLATFORM_URL` / `host.docker.internal` must **not** overwrite it. Hello to `10.10.*` runs inside the WireGuard container netns.

Home Box UI is published on the box WG address **`:8123`** (socat proxy in the WG netns → `homeassistant`). Edge/CF should target `https://box-….scardustech.com` → hub → `10.10.x.y:8123`.

## Apply the tunnel

| Host | How |
| --- | --- |
| **Linux / Raspberry Pi** | Enroll UI restarts the profile when Docker sock is available; otherwise `docker compose --profile wireguard up -d` |
| **Windows lab** | Import `config/wireguard/wg0.conf` into **WireGuard for Windows** during/before the countdown (Docker Desktop WG profile is unreliable) |

`AllowedIPs` must stay overlay-only (`10.10.0.0/16`) — never `0.0.0.0/0`.

## BMS change required (other team)

Extend `qr_payload()` / `enroll_payload()` so the PNG/JSON includes the **box** peer `config` (or structured fields). Keep QR under ~2 KB. Do not put user/phone private keys in the box QR.

Until BMS ships that, scan still enrolls; WireGuard shows **not in QR**.
