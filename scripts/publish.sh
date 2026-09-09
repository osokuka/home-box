#!/usr/bin/env bash
# Build and push Home Box images to Docker Hub (default: avniademi).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
SKIP_LOGIN="${SKIP_DOCKER_LOGIN:-0}"

if [ "${SKIP_LOGIN}" != "1" ]; then
  bash "${SCRIPT_DIR}/docker-login.sh"
fi

USER_NAME="${DOCKERHUB_USER:-avniademi}"
if [ -f "${SCRIPT_DIR}/docker-hub.env" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    key="$(echo "$key" | tr -d '[:space:]')"
    if [ "$key" = "DOCKERHUB_USER" ] && [ -n "$val" ]; then
      USER_NAME="$(echo "$val" | tr -d '[:space:]' | tr -d \"\' )"
    fi
  done < "${SCRIPT_DIR}/docker-hub.env"
fi

TAG="${HOME_BOX_TAG:-0.1.0}"
LATEST="${PUSH_LATEST:-1}"

push_tagged() {
  local name="$1"
  docker push "${USER_NAME}/${name}:${TAG}"
  if [ "${LATEST}" = "1" ]; then
    docker tag "${USER_NAME}/${name}:${TAG}" "${USER_NAME}/${name}:latest"
    docker push "${USER_NAME}/${name}:latest"
  fi
}

echo "Building ${USER_NAME}/*:${TAG}"
docker build -t "${USER_NAME}/home-box:${TAG}" ./image
docker build -t "${USER_NAME}/home-box-enroll:${TAG}" -f ./platform/Dockerfile.enroll ./platform
docker build -t "${USER_NAME}/home-box-tuya-import:${TAG}" -f ./platform/Dockerfile.tuya-import ./platform
docker build -t "${USER_NAME}/home-box-mcp:${TAG}" -f ./platform/Dockerfile.mcp ./platform
docker build -t "${USER_NAME}/home-box-lan-router:${TAG}" -f ./platform/Dockerfile.lan-router .
docker build -t "${USER_NAME}/home-box-gateway:${TAG}" -f ./nginx/Dockerfile ./nginx

docker tag "${USER_NAME}/home-box:${TAG}" home-box:local
docker tag "${USER_NAME}/home-box-enroll:${TAG}" home-box-enroll:local
docker tag "${USER_NAME}/home-box-tuya-import:${TAG}" home-box-tuya-import:local
docker tag "${USER_NAME}/home-box-mcp:${TAG}" home-box-mcp:local

push_tagged home-box
push_tagged home-box-enroll
push_tagged home-box-tuya-import
push_tagged home-box-mcp
push_tagged home-box-lan-router
push_tagged home-box-gateway

echo "Done. Deploy from ./deploy with HOME_BOX_TAG=${TAG}"
