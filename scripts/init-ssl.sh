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

# Start nginx without SSL first
echo "### Starting nginx ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml up -d nginx

# Wait for nginx to start
sleep 5

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
    --force-renewal" certbot

# After certificate generation, create the directory and copy files
echo "### Creating symbolic links to the latest certificates ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml run --rm --entrypoint "sh" certbot -c "\
    mkdir -p /etc/letsencrypt/live/${domains[0]} && \
    latest=\$(ls -d /etc/letsencrypt/live/${domains[0]}-* | sort -V | tail -n 1) && \
    cp -L \$latest/fullchain.pem /etc/letsencrypt/live/${domains[0]}/fullchain.pem && \
    cp -L \$latest/privkey.pem /etc/letsencrypt/live/${domains[0]}/privkey.pem && \
    cp -L \$latest/chain.pem /etc/letsencrypt/live/${domains[0]}/chain.pem && \
    cp -L \$latest/cert.pem /etc/letsencrypt/live/${domains[0]}/cert.pem && \
    chown -R root:root /etc/letsencrypt/live/${domains[0]}"

echo "### Reloading nginx ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml exec nginx nginx -s reload 