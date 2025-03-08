#!/bin/bash

# Check if environment argument is provided
if [ "$1" != "staging" ] && [ "$1" != "prod" ]; then
    echo "Usage: $0 [staging|prod]"
    echo "Example: $0 staging"
    exit 1
fi

ENV=$1

# Set domain based on environment
if [ "$ENV" == "staging" ]; then
    domains=(api-staging.onlypawsapp.com)
    cert_name="api-staging.onlypawsapp.com"
else
    domains=(api.onlypawsapp.com)
    cert_name="api.onlypawsapp.com"
fi

rsa_key_size=4096
data_path="./docker/$ENV/certbot"
email="brandon.dykun@gmail.com" # Adding a valid address is strongly recommended
staging=0 # Set to 1 if you're testing your setup to avoid hitting request limits

if [ -d "$data_path" ]; then
    read -p "Existing data found for $domains. Continue and replace existing certificate? (y/N) " decision
    if [ "$decision" != "Y" ] && [ "$decision" != "y" ]; then
        exit
    fi
fi

echo "### Creating required directories ..."
mkdir -p "$data_path/conf"
mkdir -p "$data_path/www"

# Stop any running containers first
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml down

echo "### Cleaning up existing certificates ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml run --rm --entrypoint "sh" certbot -c "\
    rm -rf /etc/letsencrypt/live/* && \
    rm -rf /etc/letsencrypt/archive/* && \
    rm -rf /etc/letsencrypt/renewal/*"

echo "### Creating dummy certificate for ${domains[0]} ..."
path="/etc/letsencrypt/live/${domains[0]}"
mkdir -p "$data_path/conf/live/${domains[0]}"
mkdir -p "$data_path/conf/archive/${domains[0]}"

docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml run --rm --entrypoint "\
    mkdir -p /etc/letsencrypt/live/${domains[0]} && \
    openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 1\
    -keyout '$path/privkey.pem' \
    -out '$path/fullchain.pem' \
    -subj '/CN=localhost'" certbot

# Copy initial config for first-time setup
echo "### Setting up initial nginx config ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml exec nginx sh -c "cp /etc/nginx/templates/init.conf.template /etc/nginx/conf.d/default.conf"

# Start nginx without SSL first
echo "### Starting nginx ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml up -d nginx

# Add debug information
echo "### Checking nginx status ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml ps nginx
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml logs nginx

# Increase wait time for nginx to start
echo "### Waiting for nginx to be fully started ..."
sleep 15

# Test if nginx is responding
echo "### Testing nginx HTTP response ..."
curl -v http://localhost/.well-known/acme-challenge/test || true

# Add verification of challenge path
echo "### Creating challenge directory ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml exec nginx mkdir -p /var/www/certbot/.well-known/acme-challenge

echo "### Verifying challenge path setup ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml exec nginx ls -la /var/www/certbot/.well-known/acme-challenge || true
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml exec nginx curl -v http://localhost/.well-known/acme-challenge/ || true

echo "### Deleting dummy certificate ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml run --rm --entrypoint "\
    rm -Rf /etc/letsencrypt/live/${domains[0]} && \
    rm -Rf /etc/letsencrypt/archive/${domains[0]} && \
    rm -Rf /etc/letsencrypt/renewal/${domains[0]}.conf" certbot

echo "### Requesting Let's Encrypt certificate ..."
domain_args=""
for domain in "${domains[@]}"; do
    domain_args="$domain_args -d $domain"
done

case "$email" in
    "") email_arg="--register-unsafely-without-email" ;;
    *) email_arg="--email $email" ;;
esac

if [ $staging != "0" ]; then 
    staging_arg="--staging"
fi

docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml run --rm --entrypoint "\
    certbot certonly --webroot -w /var/www/certbot \
    $staging_arg \
    $email_arg \
    $domain_args \
    --cert-name $cert_name \
    --rsa-key-size $rsa_key_size \
    --agree-tos \
    --force-renewal \
    --debug-challenges \
    -v" certbot

# Replace the certificate update section with this simpler version
echo "### Verifying certificate path ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml run --rm --entrypoint "sh" certbot -c "\
    ls -la /etc/letsencrypt/live/${domains[0]} && \
    echo 'Certificate files are in place'"

# After certificate is obtained, copy the full config
echo "### Setting up full nginx config ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml exec nginx sh -c "cp /etc/nginx/templates/nginx.conf.template /etc/nginx/conf.d/default.conf"

echo "### Reloading nginx ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml exec nginx nginx -s reload 