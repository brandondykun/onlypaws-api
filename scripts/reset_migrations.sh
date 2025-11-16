#!/bin/bash

# This script resets the database and creates fresh migrations
# Use this after restructuring models

echo "=== Resetting Database and Migrations ==="

# Check if argument is provided, default to dev if not
if [ $# -gt 1 ]; then
    echo "Error: Too many arguments provided"
    echo "Usage: ./reset_migrations.sh [dev|test|staging|e2e|prod]"
    echo "If no argument is passed, defaults to dev"
    exit 1
fi

ENV=${1:-dev}  # Default to dev if no environment specified

# Validate the environment argument
case $ENV in
    dev|test|staging|e2e|prod)
        ;;
    *)
        echo "Error: Invalid environment specified"
        echo "Valid options are: dev, test, staging, e2e, prod"
        exit 1
        ;;
esac

# Get the current directory name
current_dir=$(basename "$(pwd)")

# If we're in the scripts directory, move up one level
if [ "$current_dir" = "scripts" ]; then
    cd .. || exit 1
fi

echo "Environment: $ENV"

# Change directory to docker folder
cd docker || exit 1

echo ""
echo "Step 1: Stopping containers..."
docker compose -f docker-compose.yml -f "$ENV/docker-compose.override.yml" down

echo ""
echo "Step 2: Removing database volume..."
docker volume rm "only-paws_only-paws-db-data-$ENV"

echo ""
echo "Step 3: Creating fresh migrations..."
docker compose -f docker-compose.yml -f "$ENV/docker-compose.override.yml" run --rm only-paws-app python manage.py makemigrations

echo ""
echo "Step 4: Starting containers (migrations will run automatically)..."
docker compose -f docker-compose.yml -f "$ENV/docker-compose.override.yml" up -d

echo ""
echo "=== Done! ==="
echo "Watch logs with: docker compose -f docker-compose.yml -f $ENV/docker-compose.override.yml logs -f"

