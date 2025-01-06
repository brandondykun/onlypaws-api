from django.core.management.base import BaseCommand
from django.db import transaction
from apps.core_app.models import ReportReason  # Replace with your actual app name


class Command(BaseCommand):
    help = "Loads initial report reasons into the database"

    def handle(self, *args, **kwargs):
        # Define your preset report reasons
        report_reasons = [
            {
                "name": "Inappropriate Content",
                "description": "Content contains inappropriate, offensive, or explicit material",
            },
            {
                "name": "Not Pet Related",
                "description": "Content is not pet related",
            },
            {
                "name": "Too Much Human",
                "description": "Content contains too much human presence and I'm not here for that",
            },
            {"name": "Other", "description": "A reason other than the ones listed"},
        ]

        try:
            with transaction.atomic():
                # Keep track of how many reasons we create
                created_count = 0

                for reason in report_reasons:
                    # Only create if it doesn't already exist
                    _, created = ReportReason.objects.get_or_create(
                        name=reason["name"],
                        defaults={"description": reason["description"]},
                    )
                    if created:
                        created_count += 1

                # Print success message
                if created_count > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully created {created_count} new report reasons"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "No new report reasons were created (all already exist)"
                        )
                    )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error loading report reasons: {str(e)}")
            )
            raise
