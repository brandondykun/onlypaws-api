#!/bin/bash

# Deployment script with maintenance mode
# This script demonstrates the proper deployment workflow with maintenance mode handling

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Default values
ENVIRONMENT="${1:-staging}"
SKIP_MAINTENANCE=false
HEALTH_CHECK_TIMEOUT=120
HEALTH_CHECK_INTERVAL=5

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        dev|staging|prod)
            ENVIRONMENT="$1"
            shift
            ;;
        --skip-maintenance)
            SKIP_MAINTENANCE=true
            shift
            ;;
        --timeout)
            HEALTH_CHECK_TIMEOUT="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [ENVIRONMENT] [OPTIONS]"
            echo ""
            echo "Arguments:"
            echo "  ENVIRONMENT           Environment to deploy to (dev|staging|prod)"
            echo ""
            echo "Options:"
            echo "  --skip-maintenance    Skip maintenance mode (for minor updates)"
            echo "  --timeout SECONDS     Health check timeout (default: 120)"
            echo "  -h, --help            Show this help message"
            echo ""
            echo "Example:"
            echo "  $0 staging"
            echo "  $0 prod --timeout 180"
            exit 0
            ;;
        *)
            shift
            ;;
    esac
done

# Validate environment
case $ENVIRONMENT in
    dev|staging|prod)
        ;;
    *)
        echo -e "${RED}Error: Invalid environment '$ENVIRONMENT'${NC}"
        echo "Valid options are: dev, staging, prod"
        exit 1
        ;;
esac

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  Deploying to: ${YELLOW}$ENVIRONMENT${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to check health
check_health() {
    local url="$1"
    local timeout="$2"
    local interval="$3"
    local elapsed=0

    echo -e "${YELLOW}Waiting for application to become healthy...${NC}"

    while [ $elapsed -lt $timeout ]; do
        # Try to get status endpoint and check response body
        if response=$(curl -s "$url" 2>/dev/null); then
            http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)
            
            # Check for HTTP 200 AND "operational" status in response body
            # This ensures Django is actually responding, not just nginx's fallback
            if [ "$http_code" = "200" ] && echo "$response" | grep -q '"status".*"operational"'; then
                echo -e "${GREEN}✓ Application is healthy (HTTP $http_code, status: operational)${NC}"
                return 0
            elif [ "$http_code" = "200" ]; then
                # Got 200 but not operational (likely nginx fallback during maintenance)
                echo "  Got HTTP 200 but status is not operational yet..."
            fi
        fi

        sleep $interval
        elapsed=$((elapsed + interval))
        echo "  Waiting... ($elapsed/${timeout}s)"
    done

    echo -e "${RED}✗ Health check timed out after ${timeout}s${NC}"
    return 1
}

# Determine the status endpoint URL based on environment
case $ENVIRONMENT in
    dev)
        STATUS_URL="http://localhost:8000/api/v1/config/status/"
        ;;
    staging)
        STATUS_URL="https://api-staging.onlypawsapp.com/api/v1/config/status/"
        ;;
    prod)
        STATUS_URL="https://api.onlypawsapp.com/api/v1/config/status/"
        ;;
esac

# Step 1: Enable maintenance mode (if not skipped and nginx is available)
if [ "$SKIP_MAINTENANCE" = false ]; then
    if [ "$ENVIRONMENT" != "dev" ]; then
        echo -e "${YELLOW}Step 1: Enabling maintenance mode...${NC}"
        if ./scripts/maintenance-on.sh; then
            MAINTENANCE_ENABLED=true
        else
            echo -e "${YELLOW}Warning: Could not enable maintenance mode (nginx may not be running)${NC}"
            MAINTENANCE_ENABLED=false
        fi
    else
        echo -e "${YELLOW}Step 1: Skipping maintenance mode for dev environment${NC}"
        MAINTENANCE_ENABLED=false
    fi
else
    echo -e "${YELLOW}Step 1: Skipping maintenance mode (--skip-maintenance)${NC}"
    MAINTENANCE_ENABLED=false
fi
echo ""

# Define services to restart (excluding nginx so maintenance mode persists)
APP_SERVICES="only-paws-app celery-worker-default celery-worker-embeddings celery-beat"

# Step 2: Stop application containers (keep nginx running for maintenance page)
echo -e "${YELLOW}Step 2: Stopping application containers...${NC}"
if [ "$MAINTENANCE_ENABLED" = true ]; then
    # Keep nginx running to serve maintenance page
    docker compose -f docker/docker-compose.yml -f "docker/$ENVIRONMENT/docker-compose.override.yml" stop $APP_SERVICES || true
    echo -e "${GREEN}✓ Application containers stopped (nginx still serving maintenance page)${NC}"
else
    # No maintenance mode - can stop everything
    docker compose -f docker/docker-compose.yml -f "docker/$ENVIRONMENT/docker-compose.override.yml" down || true
    echo -e "${GREEN}✓ Containers stopped${NC}"
fi
echo ""

# Step 3: Pull latest images / Rebuild
echo -e "${YELLOW}Step 3: Rebuilding application...${NC}"
docker compose -f docker/docker-compose.yml -f "docker/$ENVIRONMENT/docker-compose.override.yml" build --no-cache only-paws-app
echo -e "${GREEN}✓ Build complete${NC}"
echo ""

# Step 4: Start containers
echo -e "${YELLOW}Step 4: Starting containers...${NC}"
if [ "$MAINTENANCE_ENABLED" = true ]; then
    # Start only app services (nginx is already running)
    docker compose -f docker/docker-compose.yml -f "docker/$ENVIRONMENT/docker-compose.override.yml" up -d $APP_SERVICES
    echo -e "${GREEN}✓ Application containers started${NC}"
else
    # Start everything
    docker compose -f docker/docker-compose.yml -f "docker/$ENVIRONMENT/docker-compose.override.yml" up -d
    echo -e "${GREEN}✓ Containers started${NC}"
fi
echo ""

# Step 5: Wait for health check
echo -e "${YELLOW}Step 5: Running health checks...${NC}"
sleep 10  # Give containers time to initialize

if check_health "$STATUS_URL" "$HEALTH_CHECK_TIMEOUT" "$HEALTH_CHECK_INTERVAL"; then
    echo -e "${GREEN}✓ Health check passed${NC}"
else
    echo -e "${RED}✗ Health check failed${NC}"
    echo ""
    echo "Container logs:"
    docker compose -f docker/docker-compose.yml -f "docker/$ENVIRONMENT/docker-compose.override.yml" logs --tail=50 only-paws-app
    
    # Don't disable maintenance mode if health check fails
    echo ""
    echo -e "${RED}Deployment failed. Maintenance mode remains ENABLED.${NC}"
    echo -e "${RED}Please investigate and manually disable maintenance mode when fixed.${NC}"
    exit 1
fi
echo ""

# Step 6: Disable maintenance mode
if [ "$MAINTENANCE_ENABLED" = true ]; then
    echo -e "${YELLOW}Step 6: Disabling maintenance mode...${NC}"
    ./scripts/maintenance-off.sh
    echo -e "${GREEN}✓ Maintenance mode disabled${NC}"
else
    echo -e "${YELLOW}Step 6: Skipping (maintenance mode was not enabled)${NC}"
fi
echo ""

echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}  Deployment complete!${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo "Environment: $ENVIRONMENT"
echo "Status URL: $STATUS_URL"
echo ""
echo "Verify deployment:"
echo "  curl $STATUS_URL"
