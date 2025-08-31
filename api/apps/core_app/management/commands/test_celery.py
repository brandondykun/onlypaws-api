"""
Management command to test Celery setup.
"""

from django.core.management.base import BaseCommand
from apps.core_app.tasks import generate_embeddings_for_missing_task
from core.celery import debug_task


class Command(BaseCommand):
    help = "Test Celery setup and task execution"

    def add_arguments(self, parser):
        parser.add_argument(
            "--test-type",
            choices=["debug", "embedding"],
            default="debug",
            help="Type of test to run (default: debug)",
        )

    def handle(self, *args, **options):
        test_type = options["test_type"]

        self.stdout.write(
            self.style.SUCCESS(f"Testing Celery with test type: {test_type}")
        )

        try:
            if test_type == "debug":
                # Test basic Celery functionality
                self.stdout.write("Queuing debug task...")
                task_result = debug_task.delay()

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Debug task queued successfully!\n"
                        f"Task ID: {task_result.id}\n"
                        f"Task status: {task_result.status}"
                    )
                )

            elif test_type == "embedding":
                # Test embedding discovery task (doesn't actually process, just finds candidates)
                self.stdout.write("Testing embedding discovery task...")
                task_result = generate_embeddings_for_missing_task.delay(
                    batch_size=5, force=False
                )

                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Embedding discovery task queued successfully!\n"
                        f"Task ID: {task_result.id}\n"
                        f"Task status: {task_result.status}"
                    )
                )

            self.stdout.write(
                self.style.WARNING(
                    "\nNote: Tasks are running in the background.\n"
                    "Check Celery worker logs to see task execution.\n"
                    "Make sure Redis and Celery workers are running."
                )
            )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(
                    f"Failed to queue Celery task: {str(e)}\n"
                    "Make sure Redis is running and Celery is properly configured."
                )
            )

            # Additional troubleshooting info
            try:
                from celery import current_app

                self.stdout.write(
                    self.style.WARNING(
                        f"Celery broker URL: {current_app.conf.broker_url}\n"
                        f"Celery result backend: {current_app.conf.result_backend}"
                    )
                )
            except Exception as config_error:
                self.stdout.write(
                    self.style.ERROR(f"Could not get Celery config: {config_error}")
                )
