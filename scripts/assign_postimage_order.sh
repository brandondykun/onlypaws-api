#!/bin/bash

# This script assigns order values to PostImages based on their ID within each Post
# Depending on the environment, it will run the command in the dev, e2e, or staging environment

# Check if at least one argument is provided
if [ $# -lt 1 ]; then
    echo "Error: At least one argument is required"
    echo "You must specify either 'dev', 'e2e' or 'staging' environment as an argument"
    echo "Usage: ./assign_postimage_order.sh <dev|e2e|staging> [--dry-run]"
    exit 1
fi

# Validate the environment argument
case $1 in
    dev|e2e|staging)
        environment=$1
        ;;
    *)
        echo "Error: Invalid environment specified"
        echo "Valid options are: dev, e2e, staging"
        exit 1
        ;;
esac

# Check for optional --dry-run flag
dry_run_flag=""
if [ $# -eq 2 ]; then
    case $2 in
        --dry-run)
            dry_run_flag="--dry-run"
            echo "Running in DRY RUN mode - no changes will be made"
            ;;
        *)
            echo "Error: Invalid second argument"
            echo "Valid option is: --dry-run"
            exit 1
            ;;
    esac
fi

# Get the current directory name
current_dir=$(basename "$(pwd)")

# If we're in the scripts directory, move up one level
if [ "$current_dir" = "scripts" ]; then
    cd .. || exit 1
fi

docker compose -f docker/docker-compose.yml -f docker/$environment/docker-compose.override.yml exec -e DJANGO_ENV=$environment only-paws-app python manage.py assign_postimage_order $dry_run_flag

