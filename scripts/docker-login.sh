#!/usr/bin/env bash
# Docker Hub login for publish scripts.
# Credentials: scripts/docker-hub.env (gitignored) or DOCKERHUB_USER / DOCKERHUB_TOKEN env.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ENV_FILE="${DOCKER_HUB_ENV_FILE:-$SCRIPT_DIR/docker-hub.env}"

USER_NAME="${DOCKERHUB_USER:-}"
TOKEN="${DOCKERHUB_TOKEN:-}"

if [ -f "$ENV_FILE" ]; then
  # shellcheck disable=SC1090
  set -a
  # Only KEY=VALUE lines; ignore comments/blank
  while IFS= read -r line || [ -n "$line" ]; do
    case "$line" in
      ''|\#*) continue ;;
    esac
    key="${line%%=*}"
    val="${line#*=}"
    key="$(echo "$key" | tr -d '[:space:]')"
    val="${val#"${val%%[![:space:]]*}"}"
    val="${val%"${val##*[![:space:]]}"}"
    val="${val%\"}"; val="${val#\"}"
    val="${val%\'}"; val="${val#\'}"
    case "$key" in
      DOCKERHUB_USER) USER_NAME="$val" ;;
      DOCKERHUB_TOKEN) TOKEN="$val" ;;
    esac
  done < "$ENV_FILE"
  set +a
fi

if [ -z "${USER_NAME}" ] || [ -z "${TOKEN}" ]; then
  echo "Missing Docker Hub credentials. Set DOCKERHUB_USER/DOCKERHUB_TOKEN or create scripts/docker-hub.env (see docker-hub.env.example)." >&2
  exit 1
fi

printf '%s' "$TOKEN" | docker login -u "$USER_NAME" --password-stdin
echo "Docker Hub login ok as ${USER_NAME}"
