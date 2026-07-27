#!/usr/bin/env bash
set -euo pipefail

docker compose -f docker-compose.preprocessing.yml build
docker compose -f docker-compose.preprocessing.yml run --rm preprocess "$@"
docker compose -f docker-compose.preprocessing.yml run --rm verify-processed
