#!/bin/bash

# Run tests
# run tests with coverage by passing coverage as the optional argument
# optionally pass an app_name to run tests for a specific app
# ex: ./test.sh <- run all tests without coverage
# ex: ./test.sh coverage <- run all tests with coverage
# ex: ./test.sh posts_app <- run tests for posts_app without coverage
# ex: ./test.sh coverage posts_app <- run tests for posts_app with coverage

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

# Parse arguments
COVERAGE=false
APP_NAME="apps"

for arg in "$@"; do
    if [ "$arg" = "coverage" ]; then
        COVERAGE=true
    else
        APP_NAME="apps/${arg}"
    fi
done

if [ "$COVERAGE" = true ]; then
    # Run tests with coverage
    echo "--------------------------------"
    echo "Running tests with coverage for: $APP_NAME"
    echo "--------------------------------"
    # Run both commands in the same container to ensure coverage data consistency
    $DOCKER_CMD "coverage run manage.py test $APP_NAME && coverage html"
    # open the coverage report in the browser
    open ../api/htmlcov/index.html
else
    # Run tests without coverage
    echo "--------------------------------"
    echo "Running tests without coverage for: $APP_NAME"
    echo "--------------------------------"
    echo "If you meant to run with coverage, pass 'coverage' as an argument"
    echo "ex: ./test.sh coverage"
    echo "--------------------------------"
    $DOCKER_CMD "python manage.py test $APP_NAME"
fi
