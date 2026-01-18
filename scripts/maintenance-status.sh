#!/bin/bash

# Check maintenance mode status
# This script checks if maintenance mode is currently enabled

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
CONTAINER_NAME="only-paws-nginx-1"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--container)
            CONTAINER_NAME="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
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

echo -e "${YELLOW}Checking maintenance mode status...${NC}"
echo ""

# Check if nginx container is running
if ! docker ps --format '{{.Names}}' | grep -q "nginx"; then
    # Try to find the correct container name
    NGINX_CONTAINER=$(docker ps --format '{{.Names}}' | grep -E "(nginx|proxy)" | head -1)
    if [ -n "$NGINX_CONTAINER" ]; then
        CONTAINER_NAME="$NGINX_CONTAINER"
    else
        echo -e "${RED}nginx container: NOT RUNNING${NC}"
        exit 1
    fi
fi

echo -e "nginx container: ${GREEN}$CONTAINER_NAME${NC}"

# Check if maintenance config file exists
if docker exec "$CONTAINER_NAME" test -f /etc/nginx/conf.d/maintenance.conf 2>/dev/null; then
    echo -e "Maintenance mode: ${YELLOW}ENABLED${NC}"
    echo ""
    echo "Maintenance config:"
    docker exec "$CONTAINER_NAME" cat /etc/nginx/conf.d/maintenance.conf
else
    echo -e "Maintenance mode: ${GREEN}DISABLED${NC}"
    echo "System is operational"
fi
