"""
Celery configuration for Only Paws API.
"""

import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "core.settings")

app = Celery("onlypaws")

# Using a string here means the worker doesn't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object("django.conf:settings", namespace="CELERY")

# Load task modules from all registered Django apps.
app.autodiscover_tasks()

# Optional: Configure task routes for different queues
app.conf.task_routes = {
    "apps.core_app.tasks.generate_image_embedding_task": {"queue": "embeddings"},
    "apps.core_app.tasks.batch_generate_embeddings_task": {"queue": "embeddings"},
    # Email tasks go to default queue for fast processing
    "apps.user_app.tasks.send_verification_email_task": {"queue": "default"},
    "apps.user_app.tasks.send_reset_password_email_task": {"queue": "default"},
    "apps.user_app.tasks.send_email_change_email_task": {"queue": "default"},
    "apps.user_app.tasks.send_email_change_confirmation_task": {"queue": "default"},
    # Notification tasks go to default queue for real-time delivery
    "apps.notifications_app.tasks.send_notification_task": {"queue": "default"},
    "apps.notifications_app.tasks.create_post_like_notification_task": {"queue": "default"},
    "apps.notifications_app.tasks.create_comment_like_notification_task": {"queue": "default"},
    "apps.notifications_app.tasks.create_comment_notification_task": {"queue": "default"},
    "apps.notifications_app.tasks.create_follow_notification_task": {"queue": "default"},
    "apps.notifications_app.tasks.send_system_message_task": {"queue": "default"},
    "apps.notifications_app.tasks.cleanup_old_notifications_task": {"queue": "maintenance"},
}

# Configure worker settings for different task types
app.conf.task_annotations = {
    "apps.core_app.tasks.generate_image_embedding_task": {
        "rate_limit": "60/m",  # Increased to 60 tasks per minute for better user experience
        "time_limit": 600,  # 10 minutes timeout
        "soft_time_limit": 540,  # 9 minutes soft timeout
    },
    "apps.core_app.tasks.batch_generate_embeddings_task": {
        "rate_limit": "10/m",  # Increased batch processing rate
        "time_limit": 3600,  # 1 hour timeout for batch jobs
        "soft_time_limit": 3300,  # 55 minutes soft timeout
    },
    # Email task settings - fast processing with reasonable timeouts
    "apps.user_app.tasks.send_verification_email_task": {
        "rate_limit": "100/m",  # Allow high throughput for emails
        "time_limit": 60,  # 1 minute timeout
        "soft_time_limit": 45,  # 45 seconds soft timeout
    },
    "apps.user_app.tasks.send_reset_password_email_task": {
        "rate_limit": "100/m",
        "time_limit": 60,
        "soft_time_limit": 45,
    },
    "apps.user_app.tasks.send_email_change_email_task": {
        "rate_limit": "100/m",
        "time_limit": 60,
        "soft_time_limit": 45,
    },
    "apps.user_app.tasks.send_email_change_confirmation_task": {
        "rate_limit": "100/m",
        "time_limit": 60,
        "soft_time_limit": 45,
    },
    # Notification task settings - high priority for real-time delivery
    "apps.notifications_app.tasks.send_notification_task": {
        "rate_limit": "200/m",  # High throughput for notifications
        "time_limit": 30,  # Quick timeout for real-time delivery
        "soft_time_limit": 25,
    },
    "apps.notifications_app.tasks.create_post_like_notification_task": {
        "rate_limit": "200/m",
        "time_limit": 30,
        "soft_time_limit": 25,
    },
    "apps.notifications_app.tasks.create_comment_like_notification_task": {
        "rate_limit": "200/m",
        "time_limit": 30,
        "soft_time_limit": 25,
    },
    "apps.notifications_app.tasks.create_comment_notification_task": {
        "rate_limit": "200/m",
        "time_limit": 30,
        "soft_time_limit": 25,
    },
    "apps.notifications_app.tasks.create_follow_notification_task": {
        "rate_limit": "200/m",
        "time_limit": 30,
        "soft_time_limit": 25,
    },
    "apps.notifications_app.tasks.send_system_message_task": {
        "rate_limit": "100/m",
        "time_limit": 30,
        "soft_time_limit": 25,
    },
    "apps.notifications_app.tasks.cleanup_old_notifications_task": {
        "rate_limit": "1/h",  # Run once per hour max
        "time_limit": 300,  # 5 minutes timeout
        "soft_time_limit": 270,
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
