#!/bin/bash

# Check maintenance mode status
# This script checks if maintenance mode is currently enabled in nginx and Django

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

echo -e "${YELLOW}Checking maintenance mode status...${NC}"
echo ""

# Check if nginx container is running
if ! docker ps --format '{{.Names}}' | grep -q "nginx"; then
    # Try to find the correct container name
    FOUND_NGINX=$(docker ps --format '{{.Names}}' | grep -E "(nginx|proxy)" | head -1)
    if [ -n "$FOUND_NGINX" ]; then
        NGINX_CONTAINER="$FOUND_NGINX"
    else
        echo -e "${RED}nginx container: NOT RUNNING${NC}"
        NGINX_CONTAINER=""
    fi
fi

# Check if Django container is running
if ! docker ps --format '{{.Names}}' | grep -q "$DJANGO_CONTAINER"; then
    # Try to find the correct container name
    FOUND_DJANGO=$(docker ps --format '{{.Names}}' | grep -E "(django|app)" | head -1)
    if [ -n "$FOUND_DJANGO" ]; then
        DJANGO_CONTAINER="$FOUND_DJANGO"
    else
        DJANGO_CONTAINER=""
    fi
fi

NGINX_MAINTENANCE=false
DJANGO_MAINTENANCE=false

# Check nginx maintenance status
if [ -n "$NGINX_CONTAINER" ]; then
    echo -e "nginx container: ${GREEN}$NGINX_CONTAINER${NC}"
    if docker exec "$NGINX_CONTAINER" test -f /etc/nginx/maintenance.d/maintenance.conf 2>/dev/null; then
        echo -e "  nginx maintenance flag: ${YELLOW}ENABLED${NC}"
        NGINX_MAINTENANCE=true
    else
        echo -e "  nginx maintenance flag: ${GREEN}DISABLED${NC}"
    fi
else
    echo -e "nginx container: ${RED}NOT RUNNING${NC}"
fi

# Check Django maintenance status
if [ -n "$DJANGO_CONTAINER" ]; then
    echo -e "Django container: ${GREEN}$DJANGO_CONTAINER${NC}"
    if docker exec "$DJANGO_CONTAINER" test -f /tmp/maintenance_mode.json 2>/dev/null; then
        echo -e "  Django maintenance flag: ${YELLOW}ENABLED${NC}"
        DJANGO_MAINTENANCE=true
        echo "  Django maintenance config:"
        docker exec "$DJANGO_CONTAINER" cat /tmp/maintenance_mode.json | sed 's/^/    /'
    else
        echo -e "  Django maintenance flag: ${GREEN}DISABLED${NC}"
    fi
else
    echo -e "Django container: ${RED}NOT RUNNING${NC}"
fi

echo ""

# Overall status
if [ "$NGINX_MAINTENANCE" = true ] && [ "$DJANGO_MAINTENANCE" = true ]; then
    echo -e "Overall status: ${YELLOW}MAINTENANCE MODE ENABLED${NC}"
elif [ "$NGINX_MAINTENANCE" = true ] || [ "$DJANGO_MAINTENANCE" = true ]; then
    echo -e "Overall status: ${RED}PARTIAL (flags out of sync!)${NC}"
    echo "  Run maintenance-on.sh or maintenance-off.sh to sync"
else
    echo -e "Overall status: ${GREEN}OPERATIONAL${NC}"
fi
