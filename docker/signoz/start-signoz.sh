#!/bin/bash

# Start the SigNoz observability stack.
# Creates the shared 'observability' network if it doesn't exist.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

docker network create observability 2>/dev/null || true

docker compose -f "$SCRIPT_DIR/docker-compose.signoz.yml" up -d
