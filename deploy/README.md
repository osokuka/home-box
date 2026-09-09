# Deploy Home Box from Docker Hub

## Quick start

### Linux / Pi

```bash
cd deploy
chmod +x deploy.sh
./deploy.sh
```

### Windows (Docker Desktop)

```powershell
cd deploy
.\deploy.ps1
```

The script writes a local `.env` (timezone, port, data dir, LAN SOCKS flag). **No BMS tokens or passwords** are required — open `/enroll/` and scan the prepare-box QR.

## Images (`avniademi/*`)

| Image | Role |
| --- | --- |
| `avniademi/home-box` | Home Assistant Core + Home Box overlays |
| `avniademi/home-box-enroll` | Enroll UI + sensory-feed agent |
| `avniademi/home-box-tuya-import` | Tuya CSV import |
| `avniademi/home-box-mcp` | MCP server |
| `avniademi/home-box-lan-router` | Privacy egress (+ optional lab SOCKS) |
| `avniademi/home-box-gateway` | nginx edge on host port 8123 |

## Publish (maintainers)

Credentials live in **gitignored** `scripts/docker-hub.env` (copy from `docker-hub.env.example`). Do not commit the PAT.

```powershell
# scripts/docker-hub.env already loads on publish
.\scripts\docker-login.ps1
.\scripts\publish.ps1 -RegistryUser avniademi -Tag 0.1.0
```

```bash
cp scripts/docker-hub.env.example scripts/docker-hub.env   # once
# edit DOCKERHUB_TOKEN=
./scripts/docker-login.sh
./scripts/publish.sh
```

Lab development still uses the repo-root `compose.yaml` with bind mounts.
