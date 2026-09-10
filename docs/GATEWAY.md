# Home Box HTTP gateway (single host port)

Only **one** host port is published: **TCP 8123** (`HOME_BOX_HTTP_PORT`).

`gateway` (nginx) path-routes to containers on the Docker network. Other services must not publish host ports.

| URL | Upstream |
| --- | --- |
| `http://<box>:8123/` | `homeassistant:8123` (WebSocket upgraded) |
| `http://<box>:8123/enroll/` | `enroll-ui:8099` |
| `http://<box>:8123/import/` | `tuya-import:8098` |
| `http://<box>:8123/mcp/sse` | `home-box-mcp:8100` |

Config: [`nginx/home-box.conf`](../nginx/home-box.conf).

Enroll / import UIs set `PUBLIC_BASE_PATH` so browser `fetch` calls stay under `/enroll` and `/import` (nginx strips the prefix toward the app).

WireGuard remains a **client** (no host `51820/udp`). Remote HA still uses the overlay socat proxy on the box WG address `:8123`.
