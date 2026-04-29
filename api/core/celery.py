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


@app.on_after_finalize.connect
def _init_telemetry_on_ready(**kwargs):
    """Init telemetry after Celery has finalized (Django fully loaded, dictConfig applied)."""
    from core.telemetry import init_telemetry
    init_telemetry()

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
    # Account deletion task goes to maintenance queue
    "apps.user_app.tasks.delete_expired_accounts_task": {"queue": "maintenance"},
    # Moderation tasks go to default queue
    "apps.moderation_app.tasks.log_profanity_detection_task": {"queue": "default"},
    # Recommendation tasks (preference embeddings, popularity refresh) go to recommendations queue
    "apps.recommendations_app.tasks.update_profile_preference_embedding_task": {"queue": "recommendations"},
    "apps.recommendations_app.tasks.update_stale_preference_embeddings_task": {"queue": "recommendations"},
    "apps.recommendations_app.tasks.nightly_preference_embedding_refresh_task": {"queue": "recommendations"},
    "apps.recommendations_app.tasks.refresh_popularity_cache_task": {"queue": "recommendations"},
    "apps.recommendations_app.tasks.refresh_heavily_reported_profiles_task": {"queue": "recommendations"},
    # Retention task goes to maintenance queue
    "apps.interactions_app.tasks.cleanup_old_post_interactions_task": {"queue": "maintenance"},
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
    "apps.user_app.tasks.delete_expired_accounts_task": {
        "rate_limit": "1/h",
        "time_limit": 300,
        "soft_time_limit": 270,
    },
    # Moderation task settings - best-effort logging
    "apps.moderation_app.tasks.log_profanity_detection_task": {
        "rate_limit": "200/m",
        "time_limit": 30,
        "soft_time_limit": 25,
    },
    # Recommendation task settings
    "apps.recommendations_app.tasks.update_profile_preference_embedding_task": {
        "rate_limit": "120/m",  # comfortably above the steady-state recompute load
        "time_limit": 60,  # weighted-average over <=500 events should be sub-second
        "soft_time_limit": 50,
    },
    "apps.recommendations_app.tasks.update_stale_preference_embeddings_task": {
        "rate_limit": "1/h",  # only one sweep can run at a time even on overlap
        "time_limit": 600,
        "soft_time_limit": 540,
    },
    "apps.recommendations_app.tasks.nightly_preference_embedding_refresh_task": {
        "rate_limit": "1/h",
        "time_limit": 1800,
        "soft_time_limit": 1500,
    },
    "apps.recommendations_app.tasks.refresh_popularity_cache_task": {
        "rate_limit": "4/h",  # comfortably above the every-30-min cadence
        "time_limit": 300,
        "soft_time_limit": 270,
    },
    "apps.recommendations_app.tasks.refresh_heavily_reported_profiles_task": {
        "rate_limit": "20/h",  # comfortably above the every-5-min cadence
        "time_limit": 60,
        "soft_time_limit": 50,
    },
    "apps.interactions_app.tasks.cleanup_old_post_interactions_task": {
        "rate_limit": "1/h",
        "time_limit": 1800,  # 30 min hard ceiling; chunked deletes shouldn't approach this
        "soft_time_limit": 1500,
    },
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
