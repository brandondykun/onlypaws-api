#!/bin/bash

# Start the SigNoz observability stack.
# Creates the shared 'observability' network if it doesn't exist.

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
COMPOSE_FILE="$SCRIPT_DIR/docker-compose.signoz.yml"

docker network create observability 2>/dev/null || true

docker compose -f "$COMPOSE_FILE" up -d

# Reconnect any running app containers to the observability network.
# If the network was recreated, existing containers hold stale references.
for container in $(docker ps --format '{{.Names}}' | grep -i onlypaws); do
    docker network disconnect observability "$container" 2>/dev/null || true
    docker network connect observability "$container" 2>/dev/null || true
done

echo "SigNoz stack is running."
