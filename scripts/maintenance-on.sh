#!/bin/bash

# Enable maintenance mode for nginx and Django
# This script creates maintenance flag files and reloads nginx

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Default values
NGINX_CONTAINER="only-paws-nginx-1"
DJANGO_CONTAINER="onlypaws_django"
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
            echo "  -m, --message MSG          Custom maintenance message"
            echo "  -e, --end-time TIME        Estimated end time (ISO format)"
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

echo -e "${YELLOW}Enabling maintenance mode...${NC}"

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

# Create nginx maintenance config content
MAINTENANCE_CONFIG="set \$maintenance_mode 1;"

# Create the maintenance config file inside nginx container
# Using /etc/nginx/maintenance.d/ to avoid conflict with default conf.d includes at http level
echo -e "${YELLOW}Creating nginx maintenance flag...${NC}"
docker exec "$NGINX_CONTAINER" sh -c "mkdir -p /etc/nginx/maintenance.d && echo '$MAINTENANCE_CONFIG' > /etc/nginx/maintenance.d/maintenance.conf"

# Create Django maintenance flag file
if [ -n "$DJANGO_CONTAINER" ]; then
    echo -e "${YELLOW}Creating Django maintenance flag...${NC}"
    # Build JSON for Django's maintenance flag
    if [ -n "$END_TIME" ]; then
        DJANGO_FLAG="{\"message\": \"$MESSAGE\", \"end_time\": \"$END_TIME\", \"allow_admin\": false}"
    else
        DJANGO_FLAG="{\"message\": \"$MESSAGE\", \"end_time\": null, \"allow_admin\": false}"
    fi
    docker exec "$DJANGO_CONTAINER" sh -c "echo '$DJANGO_FLAG' > /tmp/maintenance_mode.json"
fi

# Test nginx configuration
echo -e "${YELLOW}Testing nginx configuration...${NC}"
if docker exec "$NGINX_CONTAINER" nginx -t 2>&1; then
    # Reload nginx gracefully
    echo -e "${YELLOW}Reloading nginx...${NC}"
    docker exec "$NGINX_CONTAINER" nginx -s reload
    
    echo -e "${GREEN}✓ Maintenance mode ENABLED${NC}"
    echo -e "  Message: $MESSAGE"
    if [ -n "$END_TIME" ]; then
        echo -e "  Estimated end time: $END_TIME"
    fi
    echo ""
    echo -e "${YELLOW}Note: The status endpoint /api/v1/config/status/ remains accessible${NC}"
else
    echo -e "${RED}Error: nginx configuration test failed${NC}"
    # Remove the invalid configs
    docker exec "$NGINX_CONTAINER" rm -f /etc/nginx/maintenance.d/maintenance.conf
    if [ -n "$DJANGO_CONTAINER" ]; then
        docker exec "$DJANGO_CONTAINER" rm -f /tmp/maintenance_mode.json
    fi
    exit 1
fi
