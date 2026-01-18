#!/bin/bash

# Disable maintenance mode for nginx and Django
# This script removes maintenance flag files and reloads nginx

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
NGINX_CONTAINER="only-paws-nginx-1"
DJANGO_CONTAINER="onlypaws_django"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -c|--container)
            NGINX_CONTAINER="$2"
            shift 2
            ;;
        --django-container)
            DJANGO_CONTAINER="$2"
            shift 2
            ;;
        -h|--help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  -c, --container NAME       Nginx container name (default: only-paws-nginx-1)"
            echo "  --django-container NAME    Django container name (default: onlypaws_django)"
            echo "  -h, --help                 Show this help message"
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

echo -e "${YELLOW}Disabling maintenance mode...${NC}"

# Check if nginx container is running
if ! docker ps --format '{{.Names}}' | grep -q "nginx"; then
    # Try to find the correct container name
    FOUND_NGINX=$(docker ps --format '{{.Names}}' | grep -E "(nginx|proxy)" | head -1)
    if [ -n "$FOUND_NGINX" ]; then
        NGINX_CONTAINER="$FOUND_NGINX"
        echo -e "${YELLOW}Found nginx container: $NGINX_CONTAINER${NC}"
    else
        echo -e "${RED}Error: No nginx container found running${NC}"
        echo "Available containers:"
        docker ps --format '{{.Names}}'
        exit 1
    fi
fi

# Check if Django container is running
if ! docker ps --format '{{.Names}}' | grep -q "$DJANGO_CONTAINER"; then
    # Try to find the correct container name
    FOUND_DJANGO=$(docker ps --format '{{.Names}}' | grep -E "(django|app)" | head -1)
    if [ -n "$FOUND_DJANGO" ]; then
        DJANGO_CONTAINER="$FOUND_DJANGO"
        echo -e "${YELLOW}Found Django container: $DJANGO_CONTAINER${NC}"
    else
        echo -e "${YELLOW}Warning: No Django container found, skipping Django maintenance flag${NC}"
        DJANGO_CONTAINER=""
    fi
fi

# Remove the nginx maintenance config file
echo -e "${YELLOW}Removing nginx maintenance flag...${NC}"
docker exec "$NGINX_CONTAINER" rm -f /etc/nginx/maintenance.d/maintenance.conf

# Remove Django maintenance flag file
if [ -n "$DJANGO_CONTAINER" ]; then
    echo -e "${YELLOW}Removing Django maintenance flag...${NC}"
    docker exec "$DJANGO_CONTAINER" rm -f /tmp/maintenance_mode.json
fi

# Test nginx configuration
echo -e "${YELLOW}Testing nginx configuration...${NC}"
if docker exec "$NGINX_CONTAINER" nginx -t 2>&1; then
    # Reload nginx gracefully
    echo -e "${YELLOW}Reloading nginx...${NC}"
    docker exec "$NGINX_CONTAINER" nginx -s reload
    
    echo -e "${GREEN}✓ Maintenance mode DISABLED${NC}"
    echo -e "  System is now operational"
else
    echo -e "${RED}Error: nginx configuration test failed${NC}"
    exit 1
fi
