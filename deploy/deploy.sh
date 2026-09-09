#!/usr/bin/env bash
# Deploy Home Box from Docker Hub on Linux / macOS / Pi.
# Writes .env only (no credentials required). Enroll via http://HOST:PORT/enroll/
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

TAG="${HOME_BOX_TAG:-latest}"
PORT="${HOME_BOX_HTTP_PORT:-8123}"
DATA="${HOME_BOX_DATA:-./data}"
TZ_VAL="${TZ:-$(timedatectl show -p Timezone --value 2>/dev/null || echo UTC)}"

# Sold boxes / native Linux: direct LAN. Docker Desktop Windows uses deploy.ps1 + SOCKS.
SOCKS="${ENABLE_LAN_SOCKS:-0}"

mkdir -p "${DATA}/config/wireguard"

cat > .env <<EOF
TZ=${TZ_VAL}
HOME_BOX_HTTP_PORT=${PORT}
HOME_BOX_DATA=${DATA}
HOME_BOX_TAG=${TAG}
ENABLE_LAN_SOCKS=${SOCKS}
EOF

echo "Wrote ${ROOT}/.env"
echo "  TZ=${TZ_VAL}"
echo "  HOME_BOX_HTTP_PORT=${PORT}"
echo "  HOME_BOX_DATA=${DATA}"
echo "  HOME_BOX_TAG=${TAG}"
echo "  ENABLE_LAN_SOCKS=${SOCKS}"

docker compose -f compose.yaml pull
docker compose -f compose.yaml up -d

HOST_IP="$(hostname -I 2>/dev/null | awk '{print $1}')"
HOST_IP="${HOST_IP:-localhost}"
echo
echo "Home Box is starting."
echo "  UI:     http://${HOST_IP}:${PORT}/"
echo "  Enroll: http://${HOST_IP}:${PORT}/enroll/"
echo "No BMS tokens in .env — scan the prepare-box QR on Enroll."
