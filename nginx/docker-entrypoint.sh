#!/bin/sh
set -e

# Process the nginx configuration template
envsubst '${DOMAIN}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/conf.d/nginx.conf

# Start nginx with reload script
exec /bin/sh -c 'while :; do sleep 6h & wait ${!}; nginx -s reload; done & nginx -g "daemon off;"' 