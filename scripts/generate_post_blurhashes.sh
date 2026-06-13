#!/bin/bash

# This script generates blurhash placeholders for post images in the given environment

# Check if at least one argument is provided
if [ $# -lt 1 ]; then
    echo "Error: At least one argument is required"
    echo "You must specify either 'dev', 'e2e', 'staging' or 'prod' environment as an argument"
    echo "Usage: ./generate_post_blurhashes.sh <dev|e2e|staging|prod> [--dry-run] [--force] [--post-id <id>] [--batch-size <size>]"
    exit 1
fi

# Validate the environment argument
case $1 in
    dev|e2e|staging|prod)
        environment=$1
        ;;
    *)
        echo "Error: Invalid environment specified"
        echo "Valid options are: dev, e2e, staging, prod"
        exit 1
        ;;
esac

# Remove the environment argument so remaining management command options pass through
shift

# Get the current directory name
current_dir=$(basename "$(pwd)")

# If we're in the scripts directory, move up one level
if [ "$current_dir" = "scripts" ]; then
    cd .. || exit 1
fi

echo "Generating post image blurhashes in $environment environment..."

docker compose -f docker/docker-compose.yml -f docker/$environment/docker-compose.override.yml exec -e DJANGO_ENV=$environment only-paws-app python manage.py generate_post_blurhashes "$@"
