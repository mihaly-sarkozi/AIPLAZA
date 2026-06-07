#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
exec docker compose -f docker-compose.yml -f docker-compose.debug.yml up --build "$@"
