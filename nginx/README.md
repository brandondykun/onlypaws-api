# Nginx Configuration and SSL Setup Guide

## Overview

This guide explains the nginx configuration structure and provides step-by-step instructions for setting up SSL certificates for new domains.

---

## Table of Contents

1. [Understanding the Configuration Files](#understanding-the-configuration-files)
2. [How the System Works](#how-the-system-works)
3. [Setting Up SSL for a New Domain](#setting-up-ssl-for-a-new-domain)
4. [Certificate Renewal](#certificate-renewal)
5. [Troubleshooting](#troubleshooting)

---

## Understanding the Configuration Files

The nginx setup uses two template files that serve different purposes:

### 1. `templates/nginx.conf.template` - ✅ **PRODUCTION CONFIG**

**This is the active configuration file** used in production and staging.

**Features:**
- HTTPS/SSL configuration with Let's Encrypt certificates
- WebSocket support for real-time notifications (`/ws/` endpoints)
- API endpoints (`/api/`)
- Admin interface (`/admin/`)
- Static and media file serving
- HTTP to HTTPS redirect
- Security headers

**Template Variables:**
- `${DOMAIN}` - Replaced at runtime with the actual domain from environment variable

**Location in Container:**
- Template: `/etc/nginx/templates/nginx.conf.template`
- Generated config: `/etc/nginx/conf.d/nginx.conf`

### 2. `templates/init.conf.template` - 🔧 **SSL BOOTSTRAP CONFIG**

**Used only for initial SSL certificate setup** on new domains.

**Features:**
- HTTP-only configuration (no SSL certificates required)
- Allows Certbot to validate domain ownership
- Provides `/.well-known/acme-challenge/` endpoint for Let's Encrypt
- Does NOT redirect HTTP to HTTPS during initial setup
- Simple status response for verification

**When to Use:**
- First-time deployment on a new domain
- When SSL certificates don't exist yet
- Troubleshooting SSL certificate issues

---

## How the System Works

### Container Startup Process

When the nginx container starts, the following happens:

1. **Entrypoint Script Runs** (`docker-entrypoint.sh`)
2. **Template Processing**: Uses `envsubst` to replace `${DOMAIN}` with actual domain
3. **Config Generation**: Creates `/etc/nginx/conf.d/nginx.conf` from template
4. **Nginx Starts**: Uses the generated configuration

### Template Processing

```bash
# Line 13 in docker-entrypoint.sh
envsubst '${DOMAIN}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/conf.d/nginx.conf
```

This command:
- Reads the template file
- Replaces all instances of `${DOMAIN}` with the environment variable value
- Outputs the final configuration to nginx's config directory

### Example

If `DOMAIN=api.onlypawsapp.com`, then:
```nginx
# Template:
server_name ${DOMAIN};

# Becomes:
server_name api.onlypawsapp.com;
```

---

## Setting Up SSL for a New Domain

When deploying to production with a new domain, SSL certificates must be obtained before nginx can use the full HTTPS configuration. This is a **two-stage process**.

### The SSL Bootstrap Problem

nginx requires SSL certificates to start with the production config, but Certbot requires nginx to be running on port 80 to obtain certificates. This creates a chicken-and-egg problem:

```
Production Config → Needs SSL Certs → Certbot → Needs nginx running → Production Config
```

**Solution:** Use the init config (HTTP-only) first, get certificates, then switch to production config.

---

### Stage 1: Initial Setup (Obtain SSL Certificates)

#### Step 1: Modify the Entrypoint Script

Edit `nginx/docker-entrypoint.sh` line 13:

**Change FROM:**
```bash
envsubst '${DOMAIN}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/conf.d/nginx.conf
```

**Change TO:**
```bash
envsubst '${DOMAIN}' < /etc/nginx/templates/init.conf.template > /etc/nginx/conf.d/nginx.conf
```

#### Step 2: Set Domain Environment Variable

In your `docker/prod/docker-compose.override.yml`, ensure the DOMAIN is set:

```yaml
nginx:
  environment:
    - DOMAIN=api.yourdomain.com
```

#### Step 3: Build and Start nginx

```bash
# Build the nginx image
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml build nginx

# Start the nginx container
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml up -d nginx
```

#### Step 4: Verify nginx is Running

```bash
# Check nginx logs
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml logs nginx

# Test HTTP access (should return "Ready for SSL setup")
curl http://api.yourdomain.com
```

#### Step 5: Obtain SSL Certificates

Run Certbot to request certificates from Let's Encrypt:

```bash
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml run --rm certbot certonly --webroot \
  --webroot-path=/var/www/certbot \
  --email your-email@example.com \
  --agree-tos \
  --no-eff-email \
  -d api.yourdomain.com
```

**Important Notes:**
- Replace `your-email@example.com` with your actual email
- Replace `api.yourdomain.com` with your actual domain
- Email is used for certificate expiration notifications
- DNS must be pointing to your server before running this command
- Port 80 must be accessible from the internet

#### Step 6: Verify Certificates

Check that certificates were created successfully:

```bash
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec nginx ls -la /etc/letsencrypt/live/api.yourdomain.com/
```

You should see:
- `fullchain.pem` - Full certificate chain
- `privkey.pem` - Private key
- `cert.pem` - Certificate only
- `chain.pem` - Certificate chain only

---

### Stage 2: Switch to Production Configuration

Now that certificates exist, switch to the full production config with HTTPS.

#### Step 1: Revert the Entrypoint Script

Edit `nginx/docker-entrypoint.sh` line 13 back to the original:

**Change FROM:**
```bash
envsubst '${DOMAIN}' < /etc/nginx/templates/init.conf.template > /etc/nginx/conf.d/nginx.conf
```

**Change BACK TO:**
```bash
envsubst '${DOMAIN}' < /etc/nginx/templates/nginx.conf.template > /etc/nginx/conf.d/nginx.conf
```

#### Step 2: Rebuild nginx (Without Cache)

Important: Use `--no-cache` to ensure the entrypoint changes are picked up:

```bash
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml build --no-cache nginx
```

#### Step 3: Restart nginx

```bash
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml up -d nginx
```

#### Step 4: Verify HTTPS is Working

Test the HTTPS endpoint:

```bash
# Test HTTP redirect (should redirect to HTTPS)
curl -I http://api.yourdomain.com
```

You should see:
- HTTPS working without certificate errors
- HTTP requests redirecting to HTTPS (301/302 status)
- Valid SSL certificate in browser

---

## Certificate Renewal

### Automatic Renewal

The Certbot container is configured to automatically renew certificates:

- **Renewal Check**: Every 12 hours
- **Renewal Trigger**: When certificates are within 30 days of expiration
- **nginx Reload**: Every 6 hours to pick up renewed certificates

Configuration in `docker-compose.override.yml`:
```yaml
certbot:
  image: certbot/certbot:latest
  entrypoint: "/bin/sh -c 'trap exit TERM; while :; do certbot renew; sleep 12h & wait $${!}; done;'"
```

### Manual Renewal

If you need to renew certificates manually:

```bash
# Renew all certificates
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec certbot certbot renew

# Force renewal (even if not expiring soon)
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec certbot certbot renew --force-renewal

# Reload nginx after renewal
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec nginx nginx -s reload
```

### Check Certificate Expiration

```bash
# View certificate details
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec certbot certbot certificates
```

---

## Troubleshooting

### Problem: nginx Fails to Start After Switching to Production Config

**Symptoms:**
- nginx container exits immediately
- Error: "cannot load certificate" or "no such file"

**Cause:**
- SSL certificates don't exist at expected path
- Wrong permissions on certificate files
- Incorrect domain name in configuration

**Solutions:**

1. **Verify certificates exist:**
   ```bash
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec nginx ls -la /etc/letsencrypt/live/${DOMAIN}/
   ```

2. **Check nginx error logs:**
   ```bash
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml logs nginx
   ```

3. **Verify domain in environment:**
   ```bash
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec nginx env | grep DOMAIN
   ```

4. **Test nginx configuration:**
   ```bash
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec nginx nginx -t
   ```

---

### Problem: Certbot Validation Fails

**Symptoms:**
- "Connection refused" errors during Certbot run
- "Unable to reach domain" messages
- Validation challenges fail

**Causes:**
- Port 80 not accessible from internet
- DNS not pointing to server
- Firewall blocking port 80
- Wrong config template active (production instead of init)

**Solutions:**

1. **Verify port 80 is accessible:**
   ```bash
   curl http://api.yourdomain.com
   ```

2. **Check DNS resolution:**
   ```bash
   nslookup api.yourdomain.com
   dig api.yourdomain.com
   ```

3. **Verify init config is active:**
   ```bash
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec nginx cat /etc/nginx/conf.d/nginx.conf | grep "Initial configuration"
   ```
   Should show: `# Initial configuration for certificate setup`

4. **Test Certbot validation path:**
   ```bash
   # Create test file
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec nginx sh -c 'echo "test" > /var/www/certbot/test.txt'
   
   # Access from outside
   curl http://api.yourdomain.com/.well-known/acme-challenge/test.txt
   ```

5. **Check firewall rules:**
   ```bash
   # On the server
   sudo ufw status
   sudo iptables -L -n | grep 80
   ```

---

### Problem: Changes to Template Files Not Reflected

**Symptoms:**
- Modified templates but nginx config unchanged
- Old configuration still active after rebuild

**Cause:**
- Docker build cache using old files
- Need to rebuild without cache

**Solution:**

```bash
# Rebuild without cache
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml build --no-cache nginx

# Recreate container
docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml up -d --force-recreate nginx
```

---

### Problem: WebSocket Connections Fail (404 Errors)

**Symptoms:**
- Regular HTTP/HTTPS works fine
- WebSocket connections return 404
- `/ws/notifications/` endpoint not found

**Causes:**
- Old nginx configuration without WebSocket support
- Template not properly processed
- Wrong config file being used

**Solutions:**

1. **Verify WebSocket config is present:**
   ```bash
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec nginx cat /etc/nginx/conf.d/nginx.conf | grep -A 10 "location /ws/"
   ```
   Should show the WebSocket location block with `proxy_http_version 1.1` and upgrade headers.

2. **Check template has WebSocket config:**
   ```bash
   cat nginx/templates/nginx.conf.template | grep -A 10 "location /ws/"
   ```

3. **Rebuild nginx completely:**
   ```bash
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml build --no-cache nginx
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml up -d --force-recreate nginx
   ```

---

### Problem: HTTP Requests Not Redirecting to HTTPS

**Symptoms:**
- HTTP requests work but don't redirect
- Can access site via HTTP (insecure)

**Cause:**
- Init config still active (doesn't have redirect)
- Production config not loaded

**Solution:**

1. **Verify production config is active:**
   ```bash
   docker compose -f docker/docker-compose.yml -f docker/prod/docker-compose.override.yml exec nginx cat /etc/nginx/conf.d/nginx.conf | grep "return 301"
   ```
   Should show: `return 301 https://$host$request_uri;`

2. **If not present, switch to production config** (see Stage 2 above)

---

## Additional Resources

- [Let's Encrypt Documentation](https://letsencrypt.org/docs/)
- [Certbot Documentation](https://certbot.eff.org/docs/)
- [nginx Configuration Reference](https://nginx.org/en/docs/)
- [WebSocket Proxying with nginx](https://nginx.org/en/docs/http/websocket.html)

---

## Quick Reference

### Useful Commands

```bash
# View nginx logs
docker compose logs nginx -f

# Test nginx configuration
docker compose exec nginx nginx -t

# Reload nginx (pick up config changes)
docker compose exec nginx nginx -s reload

# View generated config
docker compose exec nginx cat /etc/nginx/conf.d/nginx.conf

# Check certificate expiration
docker compose exec certbot certbot certificates

# Manual certificate renewal
docker compose exec certbot certbot renew

# Rebuild nginx from scratch
docker compose build --no-cache nginx && docker compose up -d --force-recreate nginx
```

### File Locations

| File/Directory | Purpose |
|----------------|---------|
| `nginx/templates/nginx.conf.template` | Production config template |
| `nginx/templates/init.conf.template` | Bootstrap config template |
| `nginx/docker-entrypoint.sh` | Startup script that processes templates |
| `docker/prod/docker-compose.override.yml` | Production docker-compose settings |
| `/etc/nginx/conf.d/nginx.conf` | Generated config (inside container) |
| `/etc/letsencrypt/live/${DOMAIN}/` | SSL certificates (inside container) |
| `/var/www/certbot/` | Certbot validation directory |

