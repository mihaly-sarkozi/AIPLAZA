#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
COMPOSE_FILE="${COMPOSE_FILE:-${ROOT_DIR}/docker-compose.preprod.yml}"
SKIP_HTTP_CHECK="${SKIP_HTTP_CHECK:-0}"

echo "[preprod-smoke] compose config ellenorzes: ${COMPOSE_FILE}"
docker compose -f "${COMPOSE_FILE}" config >/dev/null

echo "[preprod-smoke] futo szolgaltatasok ellenorzese"
running_services="$(docker compose -f "${COMPOSE_FILE}" ps --services --status running || true)"

required_services=("backend" "backend-worker" "frontend" "redis")
for service in "${required_services[@]}"; do
  if ! printf '%s\n' "${running_services}" | awk -v svc="${service}" '$0 == svc {found=1} END {exit !found}'; then
    echo "[preprod-smoke] hiba: a(z) '${service}' service nem fut."
    echo "[preprod-smoke] inditas: docker compose -f ${COMPOSE_FILE} up -d --build"
    exit 1
  fi
done

if [[ "${SKIP_HTTP_CHECK}" == "1" ]]; then
  echo "[preprod-smoke] HTTP check kihagyva (SKIP_HTTP_CHECK=1)."
  exit 0
fi

echo "[preprod-smoke] backend health endpoint"
curl -fsS --max-time 8 "http://localhost:8001/api/health/ready" >/dev/null

echo "[preprod-smoke] frontend endpoint"
curl -fsS --max-time 8 "http://localhost:4173/" >/dev/null

echo "[preprod-smoke] OK"
