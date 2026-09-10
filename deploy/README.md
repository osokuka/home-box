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

The script writes a local `.env` (timezone, port, data dir, LAN SOCKS flag) and seeds `data/config/secrets.yaml` with **placeholder URLs only**. **No BMS tokens, enroll secrets, or lab machine values** are in the Hub images or in `.env`. Open `/enroll/` and scan the prepare-box QR.

Images are built with `.dockerignore` so `config/`, `.env`, and `scripts/docker-hub.env` never enter the build context.

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

Scripts ask for Docker Hub username + access token interactively (nothing stored in git).

```powershell
.\scripts\publish.ps1 -Tag 0.1.0
```

```bash
chmod +x scripts/publish.sh
./scripts/publish.sh
```

Optional: `-SkipLogin` / `SKIP_DOCKER_LOGIN=1` if you already ran `docker login`.

Lab development still uses the repo-root `compose.yaml` with bind mounts.
