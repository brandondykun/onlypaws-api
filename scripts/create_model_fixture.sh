#!/bin/bash

# This script creates a fixture for a specific model in a specified app
# Depending on the environment, it will create the fixture in the dev, test, or staging folder

# Check if arguments are provided
if [ $# -ne 3 ]; then
    echo "Error: Exactly three arguments are required"
    echo "Usage: ./create_model_fixture.sh <dev|test|staging> <app_name> <model_name>"
    echo "Example: ./create_model_fixture.sh dev feedback_app feedback"
    exit 1
fi

# Validate the first argument (environment)
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

# Store the app name and model name
app_name=$2
model_name=$3

# Get the current directory name
current_dir=$(basename "$(pwd)")

# If we're in the scripts directory, move up one level
if [ "$current_dir" = "scripts" ]; then
    cd .. || exit 1
fi

# Run the command with the provided app name and model name
docker compose -f docker/docker-compose.yml -f docker/$environment/docker-compose.override.yml exec -e DJANGO_ENV=$environment only-paws-app python manage.py dumpdata --format json --indent 2 --output fixtures/$environment/${model_name}.json ${app_name}.${model_name}