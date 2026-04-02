#!/bin/bash

# Stop the SigNoz observability stack.
# Uses 'stop + rm' instead of 'down' to preserve the shared 'observability'
# network. This allows the app stack to keep its network reference intact
# so the two stacks can be restarted independently without losing connectivity.
#
# Use -v flag to also remove volumes (wipes all telemetry history).

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.signoz.yml"

if [ "$1" = "-v" ]; then
    echo "Stopping SigNoz and removing volumes..."
    docker compose -f "$COMPOSE_FILE" stop
    docker compose -f "$COMPOSE_FILE" rm -f

    # Remove named volumes explicitly (compose 'rm -v' would also remove
    # anonymous volumes, but we only want our three named ones).
    for vol in signoz_zookeeper_data signoz_clickhouse_data signoz_signoz_data; do
        docker volume rm "$vol" 2>/dev/null || true
    done
else
    echo "Stopping SigNoz (data preserved)..."
    docker compose -f "$COMPOSE_FILE" stop
    docker compose -f "$COMPOSE_FILE" rm -f
fi
