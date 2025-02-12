#!/bin/bash

# This script creates fixtures for all models in the core_app app
# Depending on the environment, it will create the fixtures in the dev or test folder

# Check if argument is provided
if [ $# -ne 1 ]; then
    echo "Error: Exactly one argument is required"
    echo "You must specify either 'dev', 'test' or 'staging' environment as an argument"
    echo "Usage: ./create_fixtures.sh <dev|test|staging>"
    exit 1
fi

# Validate the argument
case $1 in
    dev|test|staging)
        environment=$1
        ;;
    *)
        echo "Error: Invalid environment specified"
        echo "Valid options are: dev, test, staging"
        exit 1
        ;;
esac

# Get the current directory name
current_dir=$(basename "$(pwd)")

# If we're in the scripts directory, move up one level
if [ "$current_dir" = "scripts" ]; then
    cd .. || exit 1
fi

docker compose -f docker/docker-compose.yml -f docker/$environment/docker-compose.override.yml exec -e DJANGO_ENV=$environment only-paws-app python manage.py create_fixtures