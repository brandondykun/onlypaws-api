#!/bin/bash

# Check if argument is provided, default to dev if not
if [ $# -gt 1 ]; then
    echo "Error: Too many arguments provided"
    echo "Usage: ./rebuild.sh [dev|test|staging|prod]"
    echo "If no argument is passed, defaults to dev"
    exit 1
fi

ENV=${1:-dev}  # Default to dev if no environment specified

# Validate the environment argument
case $ENV in
    dev|test|staging|prod)
        ;;
    *)
        echo "Error: Invalid environment specified"
        echo "Valid options are: dev, test, staging, prod"
        exit 1
        ;;
esac

docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml build --no-cache only-paws-app
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml up 