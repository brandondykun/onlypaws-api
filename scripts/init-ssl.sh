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
else
    domains=(api.onlypawsapp.com)
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

if [ ! -e "$data_path/conf/options-ssl-nginx.conf" ] || [ ! -e "$data_path/conf/ssl-dhparams.pem" ]; then
    echo "### Downloading recommended TLS parameters ..."
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot-nginx/certbot_nginx/_internal/tls_configs/options-ssl-nginx.conf > "$data_path/conf/options-ssl-nginx.conf"
    curl -s https://raw.githubusercontent.com/certbot/certbot/master/certbot/certbot/ssl-dhparams.pem > "$data_path/conf/ssl-dhparams.pem"
fi

echo "### Creating dummy certificate for ${domains[0]} ..."
path="/etc/letsencrypt/live/${domains[0]}"
mkdir -p "$data_path/conf/live/${domains[0]}"
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml run --rm --entrypoint "\
    openssl req -x509 -nodes -newkey rsa:$rsa_key_size -days 1\
    -keyout '$path/privkey.pem' \
    -out '$path/fullchain.pem' \
    -subj '/CN=localhost'" certbot

echo "### Starting nginx ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml up --force-recreate -d nginx

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
    --rsa-key-size $rsa_key_size \
    --agree-tos \
    --force-renewal" certbot

echo "### Reloading nginx ..."
docker compose -f docker/docker-compose.yml -f docker/$ENV/docker-compose.override.yml exec nginx nginx -s reload 