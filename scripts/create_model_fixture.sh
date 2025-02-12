#!/bin/bash

# This script creates a fixture for a specific model in the core_app app
# Depending on the environment, it will create the fixture in the dev or test folder

# Check if arguments are provided
if [ $# -ne 2 ]; then
    echo "Error: Exactly two arguments are required"
    echo "Usage: ./create_model_fixture.sh <dev|test|staging> <model_name>"
    echo "Example: ./create_model_fixture.sh dev User"
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

# Store the model name
model_name=$2

# Get the current directory name
current_dir=$(basename "$(pwd)")

# If we're in the scripts directory, move up one level
if [ "$current_dir" = "scripts" ]; then
    cd .. || exit 1
fi

# Run the command with the provided model name
docker compose -f docker/docker-compose.yml -f docker/$environment/docker-compose.override.yml exec -e DJANGO_ENV=$environment only-paws-app python manage.py dumpdata --format json --indent 2 --output fixtures/$environment/${model_name}.json core_app.${model_name}