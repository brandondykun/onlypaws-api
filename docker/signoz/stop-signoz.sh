#!/bin/bash

# Stop the SigNoz observability stack.
# Use -v flag to also remove volumes (wipes all telemetry history).

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

if [ "$1" = "-v" ]; then
    echo "Stopping SigNoz and removing volumes..."
    docker compose -f "$SCRIPT_DIR/docker-compose.signoz.yml" down -v
else
    echo "Stopping SigNoz (data preserved)..."
    docker compose -f "$SCRIPT_DIR/docker-compose.signoz.yml" down
fi
