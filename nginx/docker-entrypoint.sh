#!/bin/sh
set -e

# Print the environment variables for debugging
env

# Print the contents of the templates directory
echo "Contents of /etc/nginx/templates:"
ls -la /etc/nginx/templates/

# Print the processed nginx configuration
echo "Generated nginx configuration:"
envsubst '${DOMAIN}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/conf.d/nginx.conf
cat /etc/nginx/conf.d/nginx.conf

# Start nginx with reload script
exec /bin/sh -c 'while :; do sleep 6h & wait ${!}; nginx -s reload; done & nginx -g "daemon off;"' 