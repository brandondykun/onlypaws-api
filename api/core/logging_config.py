"""
Comprehensive logging configuration for Only Paws API.

This module provides:
- Custom filters for sampling, request tracking, and PII redaction
- Multiple formatters (verbose, simple, JSON)
- Environment-specific logging configurations
- Separate log files by level and component
"""

import logging
import random
import json
from datetime import datetime
from typing import Literal


class SamplingFilter(logging.Filter):
    """
    Filter that samples log records based on a sampling rate.
    Useful for high-frequency INFO logs in production.
    
    Args:
        sample_rate: Float between 0 and 1. 0.1 = 10% of logs pass through
        min_level: Minimum level that bypasses sampling (e.g., WARNING)
    """
    
    def __init__(self, sample_rate: float = 1.0, min_level: int = logging.WARNING):
        super().__init__()
        self.sample_rate = sample_rate
        self.min_level = min_level
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Always log messages at or above min_level (WARNING, ERROR, CRITICAL)
        if record.levelno >= self.min_level:
            return True
        
        # Sample other messages
        return random.random() < self.sample_rate


class PIIRedactionFilter(logging.Filter):
    """
    Filter that redacts sensitive information from log messages.
    
    Redacts common PII patterns:
    - Email addresses
    - Tokens/Keys (anything after 'token=', 'key=', 'password=')
    - Authorization headers
    """
    
    REDACTION_PATTERNS = [
        # Email pattern
        (r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[EMAIL_REDACTED]'),
        # Token/Key/Password patterns (case insensitive)
        (r'(?i)(token|key|password|secret)[\s]*[=:][\s]*[^\s&]+', r'\1=[REDACTED]'),
        # Authorization header
        (r'(?i)authorization:[\s]*\S+', 'authorization: [REDACTED]'),
    ]
    
    def filter(self, record: logging.LogRecord) -> bool:
        import re
        
        # Redact message
        message = record.getMessage()
        for pattern, replacement in self.REDACTION_PATTERNS:
            message = re.sub(pattern, replacement, message)
        
        # Update the record's message
        record.msg = message
        record.args = ()
        
        return True


class RequestContextFilter(logging.Filter):
    """
    Adds request context to log records when available.
    Useful for tracing requests across the application.
    """
    
    def filter(self, record: logging.LogRecord) -> bool:
        # Try to get request from Django's current thread
        try:
            from django.utils.deprecation import MiddlewareMixin
            from threading import current_thread
            
            # Add request ID if available (you can add middleware to generate this)
            request_id = getattr(current_thread(), 'request_id', None)
            record.request_id = request_id or 'no-request-id'
            
            # Add user info if available
            user = getattr(current_thread(), 'user', None)
            if user and hasattr(user, 'id'):
                record.user_id = user.id
            else:
                record.user_id = 'anonymous'
                
        except (ImportError, AttributeError):
            record.request_id = 'no-request-id'
            record.user_id = 'anonymous'
        
        return True


class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON for easier parsing and querying.
    Ideal for production environments and log aggregation systems.
    """
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.now(datetime.timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'message': record.getMessage(),
        }
        
        # Add exception info if present
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        # Add extra fields
        if hasattr(record, 'request_id'):
            log_data['request_id'] = record.request_id
        if hasattr(record, 'user_id'):
            log_data['user_id'] = record.user_id
        
        # Add any extra attributes passed to the logger
        for key, value in record.__dict__.items():
            if key not in ['name', 'msg', 'args', 'created', 'filename', 'funcName',
                          'levelname', 'levelno', 'lineno', 'module', 'msecs',
                          'message', 'pathname', 'process', 'processName', 'relativeCreated',
                          'thread', 'threadName', 'exc_info', 'exc_text', 'stack_info',
                          'request_id', 'user_id']:
                try:
                    # Only add JSON-serializable values
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    pass
        
        return json.dumps(log_data)


def get_logging_config(
    environment: Literal["dev", "test", "e2e", "staging", "prod"],
    log_dir: str = "/vol/log"
) -> dict:
    """
    Generate logging configuration based on environment.
    
    Args:
        environment: The deployment environment
        log_dir: Directory where log files will be stored
    
    Returns:
        Dictionary configuration for Python's logging.config.dictConfig
    """
    
    # Common formatters
    formatters = {
        'verbose': {
            'format': '%(asctime)s [%(levelname)-8s] [%(name)s] (%(module)s.%(funcName)s:%(lineno)d) %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'simple': {
            'format': '%(asctime)s [%(levelname)-8s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'request': {
            'format': '%(asctime)s [%(levelname)-8s] [%(name)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
        'json': {
            '()': 'core.logging_config.JSONFormatter',
        },
        'celery': {
            'format': '%(asctime)s [%(levelname)-8s] [%(task_name)s:%(task_id)s] %(message)s',
            'datefmt': '%Y-%m-%d %H:%M:%S',
        },
    }
    
    # Base filters
    filters = {
        'pii_redaction': {
            '()': 'core.logging_config.PIIRedactionFilter',
        },
        'request_context': {
            '()': 'core.logging_config.RequestContextFilter',
        },
    }
    
    # Environment-specific configuration
    if environment == "dev":
        return _get_dev_config(log_dir, formatters, filters)
    elif environment == "test":
        return _get_test_config(log_dir, formatters, filters)
    elif environment == "e2e":
        return _get_e2e_test_config(log_dir, formatters, filters)
    elif environment == "staging":
        return _get_staging_config(log_dir, formatters, filters)
    elif environment == "prod":
        return _get_prod_config(log_dir, formatters, filters)
    else:
        # Fallback to dev config
        return _get_dev_config(log_dir, formatters, filters)


def _get_dev_config(log_dir: str, formatters: dict, filters: dict) -> dict:
    """Development environment: Verbose logging with console output."""
    
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'filters': filters,
        'handlers': {
            'console': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
            'console_request': {
                'level': 'DEBUG',
                'class': 'logging.StreamHandler',
                'formatter': 'request',  # Clean format for HTTP requests in console
            },
            'file_all': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-all.log',
                'formatter': 'verbose',  # Verbose format for detailed debugging
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
            'file_requests': {
                'level': 'DEBUG',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-all.log',
                'formatter': 'request',  # Clean format for HTTP requests
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
            'file_error': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-error.log',
                'formatter': 'verbose',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
            },
            'file_celery': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/celery.log',
                'formatter': 'verbose',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
            'file_security': {
                'level': 'WARNING',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/security.log',
                'formatter': 'verbose',
                'filters': ['pii_redaction'],
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
            },
        },
        'loggers': {
            # Django core loggers
            'django': {
                'handlers': ['console', 'file_all', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.request': {
                'handlers': ['console_request', 'file_requests', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.db.backends': {
                'handlers': ['console'],
                'level': 'INFO',  # Show SQL queries in dev
                'propagate': False,
            },
            'django.security': {
                'handlers': ['console', 'file_security'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.channels': {
                'handlers': ['console', 'file_all'],
                'level': 'INFO',
                'propagate': False,
            },
            # Celery loggers
            'celery': {
                'handlers': ['console', 'file_celery'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery.worker': {
                'handlers': ['console', 'file_celery'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery.task': {
                'handlers': ['console', 'file_celery'],
                'level': 'INFO',
                'propagate': False,
            },
            # Application loggers
            'apps': {
                'handlers': ['console', 'file_all', 'file_error'],
                'level': 'DEBUG',
                'propagate': False,
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['console', 'file_all'],
        },
    }


def _get_test_config(log_dir: str, formatters: dict, filters: dict) -> dict:
    """Test environment: Minimal logging to avoid cluttering test output. No console output."""
    
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'filters': filters,
        'handlers': {
            'file_test': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-test.log',
                'formatter': 'verbose',
                'maxBytes': 5242880,  # 5MB
                'backupCount': 3,
            },
            'file_error': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-test-error.log',
                'formatter': 'verbose',
                'maxBytes': 5242880,  # 5MB
                'backupCount': 3,
            },
        },
        'loggers': {
            'django': {
                'handlers': ['file_test', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.db.backends': {
                'handlers': [],  # Don't log SQL queries in tests
                'level': 'WARNING',
                'propagate': False,
            },
            'apps': {
                'handlers': ['file_test', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['file_test'],
        },
    }


def _get_e2e_test_config(log_dir: str, formatters: dict, filters: dict) -> dict:
    """E2E Test environment: Logging with console output for debugging test runs."""
    
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'filters': filters,
        'handlers': {
            'console': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'verbose',
            },
            'console_request': {
                'level': 'INFO',
                'class': 'logging.StreamHandler',
                'formatter': 'request',  # Clean format for HTTP requests in console
            },
            'file_all': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-e2e-all.log',
                'formatter': 'verbose',  # Verbose format for detailed debugging
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
            'file_requests': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-e2e-all.log',
                'formatter': 'request',  # Clean format for HTTP requests
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
            'file_error': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-e2e-error.log',
                'formatter': 'verbose',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file_all', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.request': {
                'handlers': ['console_request', 'file_requests', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.db.backends': {
                'handlers': [],  # Don't log SQL queries in tests
                'level': 'WARNING',
                'propagate': False,
            },
            'apps': {
                'handlers': ['console', 'file_all', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
        },
        'root': {
            'level': 'INFO',
            'handlers': ['console', 'file_all'],
        },
    }


def _get_staging_config(log_dir: str, formatters: dict, filters: dict) -> dict:
    """Staging environment: Nearly identical to production with slightly more verbose sampling."""
    
    # Add sampling filter for INFO logs (less aggressive than prod for easier debugging)
    filters['info_sampling'] = {
        '()': 'core.logging_config.SamplingFilter',
        'sample_rate': 0.5,  # Log 50% of INFO messages (vs 10% in prod)
        'min_level': logging.WARNING,
    }
    
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'filters': filters,
        'handlers': {
            # Console output only for critical errors (optional for debugging)
            'console': {
                'level': 'ERROR',
                'class': 'logging.StreamHandler',
                'formatter': 'json',  # JSON format to match file output
            },
            'file_info': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-info.log',
                'formatter': 'json',
                'filters': ['info_sampling', 'pii_redaction'],
                'maxBytes': 52428800,  # 50MB
                'backupCount': 10,
            },
            'file_error': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-error.log',
                'formatter': 'json',
                'filters': ['pii_redaction'],
                'maxBytes': 52428800,  # 50MB
                'backupCount': 20,
            },
            'file_warning': {
                'level': 'WARNING',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-warning.log',
                'formatter': 'json',
                'filters': ['pii_redaction'],
                'maxBytes': 52428800,  # 50MB
                'backupCount': 15,
            },
            'file_celery': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/celery.log',
                'formatter': 'json',
                'filters': ['info_sampling', 'pii_redaction'],
                'maxBytes': 52428800,  # 50MB
                'backupCount': 10,
            },
            'file_celery_error': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/celery-error.log',
                'formatter': 'json',
                'filters': ['pii_redaction'],
                'maxBytes': 52428800,  # 50MB
                'backupCount': 20,
            },
            'file_security': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/security.log',
                'formatter': 'json',
                'filters': ['pii_redaction'],
                'maxBytes': 52428800,  # 50MB
                'backupCount': 20,
            },
            'file_performance': {
                'level': 'WARNING',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/performance.log',
                'formatter': 'json',
                'maxBytes': 52428800,  # 50MB
                'backupCount': 10,
            },
        },
        'loggers': {
            'django': {
                'handlers': ['console', 'file_info', 'file_warning', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.request': {
                'handlers': ['file_info', 'file_warning', 'file_error', 'file_performance'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.security': {
                'handlers': ['console', 'file_security', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.db.backends': {
                'handlers': [],  # Don't log SQL queries in staging
                'level': 'ERROR',
                'propagate': False,
            },
            'django.channels': {
                'handlers': ['file_info', 'file_error'],
                'level': 'WARNING',  # Less verbose for channels
                'propagate': False,
            },
            'celery': {
                'handlers': ['file_celery', 'file_celery_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery.worker': {
                'handlers': ['file_celery', 'file_celery_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery.task': {
                'handlers': ['file_celery', 'file_celery_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'apps': {
                'handlers': ['file_info', 'file_warning', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
        },
        'root': {
            'level': 'WARNING',  # More restrictive like production
            'handlers': ['console', 'file_warning', 'file_error'],
        },
    }


def _get_prod_config(log_dir: str, formatters: dict, filters: dict) -> dict:
    """Production environment: Optimized logging with sampling and JSON format."""
    
    # Add sampling filter for INFO logs (more aggressive in prod)
    filters['info_sampling'] = {
        '()': 'core.logging_config.SamplingFilter',
        'sample_rate': 0.1,  # Log only 10% of INFO messages
        'min_level': logging.WARNING,
    }
    
    return {
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': formatters,
        'filters': filters,
        'handlers': {
            'file_info': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-info.log',
                'formatter': 'json',
                'filters': ['info_sampling', 'pii_redaction'],
                'maxBytes': 104857600,  # 100MB
                'backupCount': 10,
            },
            'file_error': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-error.log',
                'formatter': 'json',
                'filters': ['pii_redaction'],
                'maxBytes': 104857600,  # 100MB
                'backupCount': 30,  # Keep more error logs
            },
            'file_warning': {
                'level': 'WARNING',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/django-warning.log',
                'formatter': 'json',
                'filters': ['pii_redaction'],
                'maxBytes': 104857600,  # 100MB
                'backupCount': 20,
            },
            'file_celery': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/celery.log',
                'formatter': 'json',
                'filters': ['info_sampling', 'pii_redaction'],
                'maxBytes': 104857600,  # 100MB
                'backupCount': 10,
            },
            'file_celery_error': {
                'level': 'ERROR',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/celery-error.log',
                'formatter': 'json',
                'filters': ['pii_redaction'],
                'maxBytes': 104857600,  # 100MB
                'backupCount': 20,
            },
            'file_security': {
                'level': 'INFO',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/security.log',
                'formatter': 'json',
                'filters': ['pii_redaction'],
                'maxBytes': 104857600,  # 100MB
                'backupCount': 30,  # Keep security logs longer
            },
            'file_performance': {
                'level': 'WARNING',
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': f'{log_dir}/performance.log',
                'formatter': 'json',
                'maxBytes': 52428800,  # 50MB
                'backupCount': 10,
            },
        },
        'loggers': {
            'django': {
                'handlers': ['file_info', 'file_warning', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.request': {
                'handlers': ['file_info', 'file_warning', 'file_error', 'file_performance'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.security': {
                'handlers': ['file_security', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'django.db.backends': {
                'handlers': [],  # Don't log SQL queries in production
                'level': 'ERROR',
                'propagate': False,
            },
            'django.channels': {
                'handlers': ['file_info', 'file_error'],
                'level': 'WARNING',  # Less verbose for channels in prod
                'propagate': False,
            },
            'celery': {
                'handlers': ['file_celery', 'file_celery_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery.worker': {
                'handlers': ['file_celery', 'file_celery_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'celery.task': {
                'handlers': ['file_celery', 'file_celery_error'],
                'level': 'INFO',
                'propagate': False,
            },
            'apps': {
                'handlers': ['file_info', 'file_warning', 'file_error'],
                'level': 'INFO',
                'propagate': False,
            },
        },
        'root': {
            'level': 'WARNING',  # More restrictive in production
            'handlers': ['file_warning', 'file_error'],
        },
    }

