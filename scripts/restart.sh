#!/bin/bash

# restart.sh - Restart the only-paws-app service for a specified environment
# Usage: ./restart.sh <environment>
# Environment options: dev, staging, test, prod

set -e  # Exit on any error

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to display usage information
usage() {
    echo "Usage: $0 <environment>"
    echo ""
    echo "Arguments:"
    echo "  environment    The environment to restart (dev, staging, test, prod)"
    echo ""
    echo "Examples:"
    echo "  $0 dev         # Restart development environment"
    echo "  $0 staging     # Restart staging environment"
    echo "  $0 test        # Restart test environment"
    echo "  $0 prod        # Restart production environment"
}

# Check if exactly one argument is provided
if [ $# -ne 1 ]; then
    print_error "Invalid number of arguments."
    echo ""
    usage
    exit 1
fi

# Get the environment argument
ENVIRONMENT="$1"

# Validate environment argument
case "$ENVIRONMENT" in
    dev|staging|test|prod)
        print_info "Environment: $ENVIRONMENT"
        ;;
    *)
        print_error "Invalid environment: $ENVIRONMENT"
        print_error "Valid environments are: dev, staging, test, prod"
        echo ""
        usage
        exit 1
        ;;
esac

# Get the script directory to ensure we're working from the correct location
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
DOCKER_DIR="$PROJECT_ROOT/docker"

print_info "Script directory: $SCRIPT_DIR"
print_info "Project root: $PROJECT_ROOT"
print_info "Docker directory: $DOCKER_DIR"

# Change to the docker directory
if ! cd "$DOCKER_DIR"; then
    print_error "Failed to change to docker directory: $DOCKER_DIR"
    exit 1
fi

# Check if docker-compose.yml exists
if [ ! -f "docker-compose.yml" ]; then
    print_error "docker-compose.yml not found in $DOCKER_DIR"
    exit 1
fi

# Check if environment-specific override file exists
OVERRIDE_FILE="$ENVIRONMENT/docker-compose.override.yml"
if [ ! -f "$OVERRIDE_FILE" ]; then
    print_error "Environment override file not found: $OVERRIDE_FILE"
    exit 1
fi

print_info "Using docker-compose.yml and $OVERRIDE_FILE"

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    print_error "Docker is not running. Please start Docker and try again."
    exit 1
fi

# Check if docker-compose/docker compose is available
DOCKER_COMPOSE_CMD=""
if command -v docker-compose >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker-compose"
elif docker compose version >/dev/null 2>&1; then
    DOCKER_COMPOSE_CMD="docker compose"
else
    print_error "Neither 'docker-compose' nor 'docker compose' command is available."
    print_error "Please install Docker Compose and try again."
    exit 1
fi

print_info "Using Docker Compose command: $DOCKER_COMPOSE_CMD"

# Check if the only-paws-app service exists in the compose configuration
print_info "Checking if only-paws-app service exists..."
if ! $DOCKER_COMPOSE_CMD -f docker-compose.yml -f "$OVERRIDE_FILE" config --services | grep -q "^only-paws-app$"; then
    print_error "Service 'only-paws-app' not found in the Docker Compose configuration."
    print_info "Available services:"
    $DOCKER_COMPOSE_CMD -f docker-compose.yml -f "$OVERRIDE_FILE" config --services | sed 's/^/  - /'
    exit 1
fi

# Restart the only-paws-app service
print_info "Restarting only-paws-app service for $ENVIRONMENT environment..."

if $DOCKER_COMPOSE_CMD -f docker-compose.yml -f "$OVERRIDE_FILE" restart only-paws-app; then
    print_success "Successfully restarted only-paws-app service for $ENVIRONMENT environment."
else
    print_error "Failed to restart only-paws-app service for $ENVIRONMENT environment."
    print_error "Please check the Docker logs for more information:"
    print_error "  $DOCKER_COMPOSE_CMD -f docker-compose.yml -f $OVERRIDE_FILE logs only-paws-app"
    exit 1
fi

# Optional: Show the status of the service after restart
print_info "Checking service status..."
if $DOCKER_COMPOSE_CMD -f docker-compose.yml -f "$OVERRIDE_FILE" ps only-paws-app; then
    print_success "Service status check completed."
else
    print_warning "Could not retrieve service status, but restart command completed successfully."
fi

print_success "Restart script completed successfully!"
