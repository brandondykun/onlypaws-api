# Maintenance Mode

This document explains how to use the maintenance mode system to gracefully handle deployments, migrations, and system updates.

## Overview

The maintenance mode system provides a way to temporarily block API requests while performing system updates, showing users a friendly maintenance message instead of errors. It consists of:

1. **Status Endpoint** - Always-accessible endpoint that reports system status
2. **Django Middleware** - Blocks requests at the application level
3. **Nginx Configuration** - Blocks requests at the proxy level (staging/prod)
4. **Management Command** - Toggle maintenance mode in development
5. **Shell Scripts** - Toggle maintenance mode in staging/production

## How It Works

### Development (Django Only)
In development, maintenance mode uses a **file-based flag** at `/tmp/maintenance_mode.json`. This allows toggling maintenance mode without restarting Django.

### Staging/Production (Nginx + Django)
In staging/production, maintenance mode operates at **two levels**:
1. **Nginx level** - Blocks requests even if Django is down (uses config file)
2. **Django level** - Fallback using environment variables

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Request Flow                             │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Client Request                                                │
│        │                                                        │
│        ▼                                                        │
│   ┌─────────┐    Maintenance     ┌─────────────────────┐        │
│   │  Nginx  │───── Mode ON? ────▶│ Return 503 JSON     │        │
│   └────┬────┘        │           │ (if Django is down) │        │
│        │            No           └─────────────────────┘        │
│        ▼                                                        │
│   ┌──────────┐    Maintenance    ┌─────────────────────┐        │
│   │ Django   │──── Mode ON? ────▶│ Return 503 JSON     │        │
│   │Middleware│       │           └─────────────────────┘        │
│   └────┬─────┘       No                                         │
│        │                                                        │
│        ▼                                                        │
│   ┌─────────┐                                                   │
│   │  View   │──────▶ Normal Response                            │
│   └─────────┘                                                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Status Endpoint

The status endpoint is always accessible, even during maintenance mode:

```
GET /api/v1/config/status/
```

### Response Format

```json
{
  "status": "operational" | "maintenance",
  "message": "Optional maintenance message",
  "estimated_end_time": "2024-01-15T14:00:00Z" | null
}
```

### Response Codes

| Status | Code | Description |
|--------|------|-------------|
| Operational | 200 | System is running normally |
| Maintenance | 200 | System is in maintenance mode (from Django) |
| Maintenance | 503 | System is in maintenance mode (from Nginx fallback) |

---

## Environment-Specific Usage

### Development Environment

In development, maintenance mode is controlled via Django's environment variables and the management command.

#### Enable Maintenance Mode

```bash
# Basic usage
docker exec onlypaws_django python manage.py maintenance on

# With custom message
docker exec onlypaws_django python manage.py maintenance on \
  --message "Upgrading database schema"

# With estimated end time
docker exec onlypaws_django python manage.py maintenance on \
  --message "Scheduled maintenance" \
  --end-time "2024-01-15T14:00:00"

# Allow admin users to access during maintenance
docker exec onlypaws_django python manage.py maintenance on \
  --message "Quick update" \
  --allow-admin
```

#### Disable Maintenance Mode

```bash
docker exec onlypaws_django python manage.py maintenance off
```

#### Check Status

```bash
docker exec onlypaws_django python manage.py maintenance status
```

#### Verify via API

```bash
curl http://localhost:8000/api/v1/config/status/
```

### Staging/Production Environments

In staging and production, maintenance mode should be controlled at the **Nginx level** to ensure requests are blocked even if Django is restarting or unavailable.

#### Enable Maintenance Mode

```bash
./scripts/maintenance-on.sh

# With custom message (for logging purposes)
./scripts/maintenance-on.sh --message "Deploying v2.1.0"
```

#### Disable Maintenance Mode

```bash
./scripts/maintenance-off.sh
```

#### Check Status

```bash
./scripts/maintenance-status.sh
```

#### Verify via API

```bash
# Staging
curl https://api-staging.onlypawsapp.com/api/v1/config/status/

# Production
curl https://api.onlypawsapp.com/api/v1/config/status/
```

---

## Deployment Workflow

Use the deployment script for a safe deployment with automatic maintenance mode handling:

```bash
# Deploy to staging
./scripts/deploy-with-maintenance.sh staging

# Deploy to production
./scripts/deploy-with-maintenance.sh prod

# Deploy without maintenance mode (minor updates)
./scripts/deploy-with-maintenance.sh staging --skip-maintenance
```

### What the Deployment Script Does

1. **Enables maintenance mode** (Nginx level)
2. **Stops application containers** (keeps nginx running to serve maintenance responses)
3. **Rebuilds the application**
4. **Starts application containers** (nginx is already running)
5. **Waits for health checks** to pass
6. **Disables maintenance mode**

**Important**: The script keeps nginx running during deployment so it can serve the maintenance response. Only the Django application and Celery workers are restarted.

If the health check fails, maintenance mode remains enabled and you'll need to investigate and manually disable it.

---

## Configuration

### File-Based Flag (Development)

The management command creates a JSON file at `/tmp/maintenance_mode.json`:

```json
{
  "enabled": true,
  "message": "System is under maintenance",
  "end_time": "2024-01-15T14:00:00",
  "allow_admin": false
}
```

This file is checked on every request, so changes take effect immediately without restarting Django.

### Environment Variables (Production Fallback)

If no flag file exists, the middleware falls back to environment variables:

| Variable | Values | Description |
|----------|--------|-------------|
| `MAINTENANCE_MODE` | `0` or `1` | Enable/disable maintenance mode |
| `MAINTENANCE_MESSAGE` | string | Custom message shown to users |
| `MAINTENANCE_END_TIME` | ISO 8601 | Estimated end time |
| `MAINTENANCE_ALLOW_ADMIN` | `0` or `1` | Allow admin users during maintenance |

### Excluded Paths

The following paths are **always accessible** during maintenance:

| Path | Reason |
|------|--------|
| `/api/v1/config/status/` | Status endpoint must always respond |
| `/admin/` | Admin interface for emergency access |
| `/static/` | Static files |
| `/.well-known/` | SSL certificate renewal |

---

## Testing Maintenance Mode

### Test in Development

```bash
# 1. Start the development environment
./scripts/run.sh dev

# 2. Enable maintenance mode
docker exec onlypaws_django python manage.py maintenance on --message "Testing"

# 3. Verify status endpoint works
curl http://localhost:8000/api/v1/config/status/
# Expected: {"status": "maintenance", "message": "Testing", ...}

# 4. Verify other endpoints are blocked
curl http://localhost:8000/api/v1/profile/
# Expected: 503 Service Unavailable

# 5. Disable maintenance mode
docker exec onlypaws_django python manage.py maintenance off

# 6. Verify system is operational
curl http://localhost:8000/api/v1/config/status/
# Expected: {"status": "operational", ...}
```

### Run Automated Tests

```bash
# Test status endpoint
./scripts/test.sh config_app.tests.test_status_api

# Test maintenance middleware
./scripts/test.sh core_app.tests.test_maintenance_middleware
```

---

## Troubleshooting

### Maintenance Mode Won't Disable

**Nginx level (staging/prod):**
```bash
# Check if maintenance config exists
./scripts/maintenance-status.sh

# Force remove maintenance config
docker exec <nginx-container> rm -f /etc/nginx/conf.d/maintenance.conf
docker exec <nginx-container> nginx -s reload
```

**Django level (dev):**
```bash
# Check if flag file exists
docker exec onlypaws_django ls -la /tmp/maintenance_mode.json

# Force remove flag file
docker exec onlypaws_django rm -f /tmp/maintenance_mode.json

# Or use management command
docker exec onlypaws_django python manage.py maintenance off
```

### Status Endpoint Returns 503

If the status endpoint itself returns 503:
1. Django is completely down
2. Nginx is serving the fallback response

Check Django logs:
```bash
docker logs onlypaws_django --tail=100
```

### Requests Still Getting Through

1. **Check Nginx config was reloaded:**
   ```bash
   docker exec <nginx-container> nginx -t
   docker exec <nginx-container> nginx -s reload
   ```

2. **Check middleware is in settings:**
   Verify `MaintenanceModeMiddleware` is in `MIDDLEWARE` in `settings.py`

3. **Check environment variable:**
   ```bash
   docker exec onlypaws_django env | grep MAINTENANCE_MODE
   ```

### Health Check Failing During Deployment

1. **Increase timeout:**
   ```bash
   ./scripts/deploy-with-maintenance.sh staging --timeout 180
   ```

2. **Check container logs:**
   ```bash
   docker logs onlypaws_django --tail=100
   ```

3. **Manually disable maintenance mode:**
   ```bash
   ./scripts/maintenance-off.sh
   ```

---

## Best Practices

1. **Always use maintenance mode for:**
   - Database migrations
   - Major version deployments
   - Infrastructure changes

2. **Skip maintenance mode for:**
   - Minor code changes
   - Config updates that don't require restart

3. **Test the deployment script** in staging before production

4. **Monitor the status endpoint** from external monitoring services

5. **Set realistic estimated end times** to inform users

6. **Keep maintenance windows short** - aim for under 5 minutes

---

## Mobile App Integration

The React Native app should:

1. **Check status on app launch:**
   ```javascript
   const response = await fetch('/api/v1/config/status/');
   const { status, message } = await response.json();
   
   if (status === 'maintenance') {
     showMaintenanceScreen(message);
   }
   ```

2. **Handle 503 responses globally:**
   ```javascript
   if (response.status === 503) {
     const { message } = await response.json();
     showMaintenanceScreen(message);
   }
   ```

3. **Implement retry logic** with exponential backoff

4. **Respect `Retry-After` header** (defaults to 300 seconds)
