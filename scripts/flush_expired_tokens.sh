#!/bin/bash

# This script flushes expired JWT tokens from the database for the given environment
# It removes expired tokens from the OutstandingToken and BlacklistedToken tables
# to prevent the token tables from growing indefinitely.

# Check if argument is provided
if [ $# -ne 1 ]; then
    echo "Error: Exactly one argument is required"
    echo "Usage: ./flush_expired_tokens.sh <dev|staging|test|e2e|prod>"
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

echo "Flushing expired JWT tokens in $environment environment..."

# Run the flushexpiredtokens management command
docker compose -f docker/docker-compose.yml -f docker/$environment/docker-compose.override.yml exec -e DJANGO_ENV=$environment only-paws-app python manage.py flushexpiredtokens

if [ $? -eq 0 ]; then
    echo "Successfully flushed expired tokens."
else
    echo "Error: Failed to flush expired tokens."
    exit 1
fi

