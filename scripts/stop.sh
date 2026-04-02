#!/bin/bash

# This script stops the docker compose file for the given environment.
# Uses 'stop + rm' instead of 'down' to preserve the shared 'observability'
# network, allowing SigNoz and the app to be restarted independently.

# Check if argument is provided
if [ $# -ne 1 ]; then
    echo "Error: Exactly one argument is required"
    echo "Usage: ./stop.sh <dev|staging|test|e2e|prod>"
    exit 1
fi

# Validate the argument
case $1 in
    dev|staging|test|e2e|prod)
        environment=$1
        ;;
    *)
        echo "Error: Invalid environment specified"
        echo "Valid options are: dev, staging, test, e2e, prod"
        exit 1
        ;;
esac

# Get the current directory name
current_dir=$(basename "$(pwd)")

# If we're in the scripts directory, move up one level
if [ "$current_dir" = "scripts" ]; then
    cd .. || exit 1
fi

# Change directory to docker folder
cd docker || exit 1

# Stop and remove containers without tearing down networks
docker compose -f docker-compose.yml -f "$environment/docker-compose.override.yml" stop
docker compose -f docker-compose.yml -f "$environment/docker-compose.override.yml" rm -f
