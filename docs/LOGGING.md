# Logging Documentation - Only Paws API

## Overview

This document describes the comprehensive logging system implemented for the Only Paws API. The logging configuration is environment-aware, providing different log levels, sampling rates, and output formats based on the deployment environment.

## Key Features

✅ **Environment-Specific Configuration** - Different logging behavior for dev, test, staging, and production  
✅ **Separate Log Files by Level** - Errors, warnings, and info logs in separate files  
✅ **Log Rotation** - Automatic rotation to prevent disk space issues  
✅ **PII Redaction** - Automatic redaction of sensitive information  
✅ **Production Sampling** - Configurable sampling rates to reduce log volume  
✅ **JSON Format** - Structured logging for production environments  
✅ **Celery Integration** - Dedicated logging for async tasks  
✅ **Security Logging** - Separate logs for authentication and authorization events  

## Log Files by Environment

### Development (`dev`)
Location: `/vol/log/` (mounted from `./logs/`)

- `django-all.log` - All logs (DEBUG level and above) with verbose formatting
- `django-error.log` - Error and critical logs only
- `celery.log` - Celery worker and task logs
- `security.log` - Authentication, authorization, and security events

**Features:**
- Console output enabled (verbose)
- SQL query logging enabled
- No sampling (100% of logs)
- Rotating file handler: 10MB max, 5-10 backups

### Test (`test`)
Location: `/vol/log/` (mounted from `./logs/`)

- `django-test.log` - General test logs (INFO and above)
- `django-test-error.log` - Test errors only

**Features:**
- No console output (clean test output)
- No SQL query logging
- No sampling
- Rotating file handler: 5MB max, 3 backups

### Staging (`staging`)
Location: `/vol/log/` (mounted from `./logs/`)

- `django-info.log` - Info level logs (JSON format, 50% sampling)
- `django-warning.log` - Warning level logs (JSON format)
- `django-error.log` - Error and critical logs (JSON format)
- `celery.log` - Celery logs (JSON format, 50% sampling)
- `celery-error.log` - Celery errors (JSON format)
- `security.log` - Security events (JSON format)
- `performance.log` - Performance issues (JSON format)

**Features:**
- Minimal console output (ERROR level only, JSON format)
- No SQL query logging
- 50% sampling for INFO logs (vs 10% in prod)
- 100% logging for WARNING and above
- **JSON format everywhere** (files and console)
- Rotating file handler: 50MB max, 10-20 backups
- PII redaction enabled
- Nearly identical to production config

### Production (`prod`)
Location: `/vol/log/` (mounted from `./logs/`)

- `django-info.log` - Info level logs (JSON format, 10% sampling)
- `django-warning.log` - Warning level logs (JSON format)
- `django-error.log` - Error and critical logs (JSON format)
- `celery.log` - Celery worker logs (JSON format, 10% sampling)
- `celery-error.log` - Celery errors only (JSON format)
- `security.log` - Security events (JSON format)
- `performance.log` - Performance-related warnings (JSON format)

**Features:**
- No console output
- No SQL query logging
- 10% sampling for INFO logs (reduce volume)
- 100% logging for WARNING and above
- JSON format for log aggregation tools
- Rotating file handler: 100MB max, 10-30 backups
- PII redaction enabled
- More restrictive root logger (WARNING level)

## Log Rotation

All environments use `RotatingFileHandler` to prevent unlimited log file growth:

- Files rotate when they reach the configured max size
- Old logs are kept as `.log.1`, `.log.2`, etc.
- Number of backups varies by environment and log type
- Error logs kept longer than info logs

## Sampling

To reduce log volume in high-traffic environments, we implement sampling for INFO-level logs:

```python
# Staging: 50% of INFO logs
# Production: 10% of INFO logs
# WARNING and above: 100% (never sampled)
```

This means:
- All errors and warnings are always logged
- Only a percentage of info logs are recorded
- Reduces I/O and storage requirements
- Sampling is configurable via `SamplingFilter`

## PII Redaction

The `PIIRedactionFilter` automatically redacts sensitive information:

- **Email addresses**: Replaced with `[EMAIL_REDACTED]`
- **Tokens/Keys/Passwords**: `token=abc123` → `token=[REDACTED]`
- **Authorization headers**: `Authorization: Bearer xxx` → `Authorization: [REDACTED]`

## Log Format

### Verbose Format (Dev)
```
2025-11-05 14:30:45 [INFO    ] [apps.user_app.views] (views.create_user:123) User created successfully
```

### JSON Format (Staging/Prod)
```json
{
  "timestamp": "2025-11-05T14:30:45.123456",
  "level": "INFO",
  "logger": "apps.user_app.views",
  "module": "views",
  "function": "create_user",
  "line": 123,
  "message": "User created successfully",
  "request_id": "abc-123-def",
  "user_id": 42
}
```

## Using Loggers in Your Code

### Basic Usage

```python
import logging

# Get a logger for your module
logger = logging.getLogger(__name__)

# Log at different levels
logger.debug("Detailed debugging information")
logger.info("General information")
logger.warning("Warning message")
logger.error("Error occurred")
logger.critical("Critical error!")
```

### With Exception Info

```python
try:
    # Some operation
    result = risky_operation()
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    # exc_info=True includes the full stack trace
```

### Adding Extra Context

```python
logger.info("User logged in", extra={
    'user_id': user.id,
    'ip_address': request.META.get('REMOTE_ADDR'),
    'user_agent': request.META.get('HTTP_USER_AGENT')
})
```

### Celery Task Logging

```python
from celery import shared_task
import logging

logger = logging.getLogger(__name__)

@shared_task(bind=True)
def my_task(self, param):
    logger.info(f"Task started: {self.request.id}")
    try:
        # Task logic
        result = do_work(param)
        logger.info(f"Task completed: {self.request.id}")
        return result
    except Exception as e:
        logger.error(f"Task failed: {self.request.id}", exc_info=True)
        raise
```

## Best Practices

### 1. Use Appropriate Log Levels

- **DEBUG**: Detailed diagnostic information (dev only)
- **INFO**: General informational messages (normal operations)
- **WARNING**: Something unexpected but handled
- **ERROR**: Error that needs attention but recoverable
- **CRITICAL**: Serious error, application may not continue

### 2. Include Context

```python
# Good
logger.error(f"Failed to process order {order_id} for user {user_id}", exc_info=True)

# Bad
logger.error("An error occurred")
```

### 3. Don't Log Sensitive Information

The PII filter helps, but be proactive:

```python
# Bad
logger.info(f"User logged in with password: {password}")

# Good
logger.info(f"User {user_id} logged in successfully")
```

### 4. Use Structured Logging in Production

When adding context, use the `extra` parameter:

```python
logger.info("Payment processed", extra={
    'order_id': order.id,
    'amount': order.total,
    'payment_method': order.payment_method,
})
```

This data will be included in the JSON output for production.

### 5. Log Performance Issues

```python
import time

start_time = time.time()
result = expensive_operation()
duration = time.time() - start_time

if duration > 5.0:  # More than 5 seconds
    logger.warning(f"Slow operation detected", extra={
        'operation': 'expensive_operation',
        'duration': duration,
    })
```

## Configuration

The logging configuration is centralized in `api/core/logging_config.py`:

- `get_logging_config(environment, log_dir)` - Main entry point
- `SamplingFilter` - Controls sampling rate
- `PIIRedactionFilter` - Redacts sensitive data
- `JSONFormatter` - Formats logs as JSON

### Customizing Logging

To modify logging behavior:

1. Edit `api/core/logging_config.py`
2. Adjust environment-specific configs (`_get_dev_config`, `_get_prod_config`, etc.)
3. Modify sampling rates, file sizes, backup counts as needed

## Monitoring and Alerting

### Recommended Setup

1. **Error Monitoring**: Watch `django-error.log` and `celery-error.log`
   - Set up alerts for ERROR and CRITICAL logs
   - Monitor error rate trends

2. **Security Monitoring**: Watch `security.log`
   - Track failed authentication attempts
   - Monitor suspicious patterns

3. **Performance Monitoring**: Watch `performance.log` (prod only)
   - Track slow requests
   - Identify bottlenecks

4. **Log Aggregation**: 
   - Use ELK Stack (Elasticsearch, Logstash, Kibana)
   - Or CloudWatch Logs for AWS deployments
   - Or Datadog/Splunk for enterprise monitoring

### Example Alerts

```bash
# Alert on multiple errors in short time
tail -f logs/django-error.log | grep -c "ERROR" 

# Monitor disk space for logs
du -sh logs/

# Check log rotation is working
ls -lh logs/*.log.*
```

## Troubleshooting

### Logs Not Appearing

1. Check the environment variable: `echo $DJANGO_ENV`
2. Verify log directory exists: `ls -la /vol/log/`
3. Check file permissions: `chmod -R 755 /vol/log/`
4. Check docker volume mount: `docker inspect <container_name>`

### Too Many Logs

1. Increase sampling rate in production
2. Reduce log levels for noisy loggers
3. Increase rotation size or decrease backup count
4. Review code for excessive logging

### Logs Missing After Rotation

1. Check `backupCount` in logging config
2. Old logs are named `.log.1`, `.log.2`, etc.
3. Implement log archival if needed

### Performance Issues

1. Reduce log level in production (WARNING instead of INFO)
2. Increase sampling rate (lower percentage)
3. Use asynchronous logging handlers if needed
4. Monitor I/O with `iostat` or similar tools

## Docker Integration

### Volume Mounts

Each environment mounts logs differently:

**Development & Test:**
```yaml
volumes:
  - ../logs:/vol/log
```

**Staging & Production:**
```yaml
volumes:
  - ../logs:/vol/log
```

All environments now mount the entire logs directory to support multiple log files.

### Accessing Logs

```bash
# From host machine
cd logs/
tail -f django-error.log

# From container
docker exec -it onlypaws_django tail -f /vol/log/django-error.log

# View all containers' logs
docker-compose logs -f
```

## Migration Notes

If upgrading from the old logging system:

1. Old single file: `django.log`
2. New multiple files: `django-all.log`, `django-error.log`, etc.
3. Docker mounts updated to support directory mounting
4. Log rotation now automatic (no manual cleanup needed)
5. PII automatically redacted in staging/prod

## Further Reading

- [Python Logging Documentation](https://docs.python.org/3/library/logging.html)
- [Django Logging](https://docs.djangoproject.com/en/5.1/topics/logging/)
- [Celery Logging](https://docs.celeryproject.org/en/stable/userguide/tasks.html#logging)
- [Structured Logging Best Practices](https://www.structlog.org/)

## Summary

The new logging system provides:
- ✅ Better organization with separate log files
- ✅ Automatic PII redaction for compliance
- ✅ Production-optimized sampling
- ✅ JSON format for easy parsing
- ✅ Automatic log rotation
- ✅ Environment-specific configurations

This makes debugging easier in development and provides production-ready logging that scales with your application.

