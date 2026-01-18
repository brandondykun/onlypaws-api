#!/bin/bash

# Enable maintenance mode for nginx
# This script creates a maintenance flag file and reloads nginx

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
CONTAINER_NAME="only-paws-nginx-1"
MESSAGE="The system is currently undergoing maintenance. Please try again later."
END_TIME=""

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -m|--message)
            MESSAGE="$2"
            shift 2
            ;;
        -e|--end-time)
            END_TIME="$2"
            shift 2
            ;;
        -c|--container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -m, --message MSG      Custom maintenance message"
            echo "  -e, --end-time TIME    Estimated end time (ISO format)"
            echo "  -c, --container NAME   Docker container name (default: only-paws-nginx-1)"
            echo "  -h, --help             Show this help message"
            exit 0
            ;;
        *)
            echo -e "${RED}Error: Unknown option $1${NC}"
            exit 1
            ;;
    esac
done

# Navigate to project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR/.." || exit 1

echo -e "${YELLOW}Enabling maintenance mode...${NC}"

# Check if nginx container is running
if ! docker ps --format '{{.Names}}' | grep -q "nginx"; then
    # Try to find the correct container name
    NGINX_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E "(nginx|proxy)" | head -1)
    if [ -n "$NGINX_CONTAINER" ]; then
        CONTAINER_NAME="$NGINX_CONTAINER"
        echo -e "${YELLOW}Found nginx container: $CONTAINER_NAME${NC}"
    else
        echo -e "${RED}Error: No nginx container found running${NC}"
        echo "Available containers:"
        docker ps --format '{{.Names}}'
        exit 1
    fi
fi

# Create maintenance config content
MAINTENANCE_CONFIG="set \$maintenance_mode 1;"

# Create the maintenance config file inside the container
echo -e "${YELLOW}Creating maintenance flag...${NC}"
docker exec "$CONTAINER_NAME" sh -c "echo '$MAINTENANCE_CONFIG' > /etc/nginx/conf.d/maintenance.conf"

# Test nginx configuration
echo -e "${YELLOW}Testing nginx configuration...${NC}"
if docker exec "$CONTAINER_NAME" nginx -t 2>&1; then
    # Reload nginx gracefully
    echo -e "${YELLOW}Reloading nginx...${NC}"
    docker exec "$CONTAINER_NAME" nginx -s reload
    
    echo -e "${GREEN}✓ Maintenance mode ENABLED${NC}"
    echo -e "  Message: $MESSAGE"
    if [ -n "$END_TIME" ]; then
        echo -e "  Estimated end time: $END_TIME"
    fi
    echo ""
    echo -e "${YELLOW}Note: The status endpoint /api/v1/config/status/ remains accessible${NC}"
else
    echo -e "${RED}Error: nginx configuration test failed${NC}"
    # Remove the invalid config
    docker exec "$CONTAINER_NAME" rm -f /etc/nginx/conf.d/maintenance.conf
    exit 1
fi
