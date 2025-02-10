#!/bin/bash

# Run tests
# run tests with coverage by passing coverage as the optional argument
# ex: ./test.sh <- run tests without coverage
# ex: ./test.sh coverage <- run tests with coverage

# Get the current directory name
current_dir=$(basename "$(pwd)")

# If we're in the scripts directory, move up one level
if [ "$current_dir" = "scripts" ]; then
    cd .. || exit 1
fi

# Change directory to docker folder
cd docker || exit 1

# Base docker compose command
DOCKER_CMD="docker compose -f docker-compose.yml -f test/docker-compose.override.yml run --rm only-paws-app sh -c"

if [ "$1" = "coverage" ]; then
    # Run tests with coverage
    echo "--------------------------------"
    echo "Running tests with coverage"
    echo "--------------------------------"
    $DOCKER_CMD "coverage run manage.py test apps"
    $DOCKER_CMD "coverage html"
    # open the coverage report in the browser
    open ../api/htmlcov/index.html
else
    # Run tests without coverage
    echo "--------------------------------"
    echo "Running tests without coverage"
    echo "--------------------------------"
    echo "If you meant to run with coverage, pass 'coverage' as an argument"
    echo "ex: ./test.sh coverage"
    echo "--------------------------------"
    $DOCKER_CMD "python manage.py test apps"
fi
