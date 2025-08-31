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
}

# Configure worker settings for embedding tasks
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
}


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup."""
    print(f"Request: {self.request!r}")
