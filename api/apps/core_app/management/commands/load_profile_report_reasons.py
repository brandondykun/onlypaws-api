from django.core.management.base import BaseCommand
from django.db import transaction
from apps.moderation_app.models import ProfileReportReason


class Command(BaseCommand):
    help = "Loads initial profile report reasons into the database"

    def handle(self, *args, **kwargs):
        profile_report_reasons = [
            {
                "name": "Impersonation",
                "description": "This profile is pretending to be someone else or another pet",
            },
            {
                "name": "Spam",
                "description": "This profile is posting spam or engaging in spam-like behavior",
            },
            {
                "name": "Harassment",
                "description": "This profile is harassing, bullying, or threatening others",
            },
            {
                "name": "Inappropriate Content",
                "description": "This profile repeatedly posts inappropriate or offensive content",
            },
            {
                "name": "Not Pet Related",
                "description": "This profile is not pet related and does not belong on the platform",
            },
            {
                "name": "Other",
                "description": "A reason other than the ones listed",
            },
        ]

        try:
            with transaction.atomic():
                created_count = 0

                for reason in profile_report_reasons:
                    _, created = ProfileReportReason.objects.get_or_create(
                        name=reason["name"],
                        defaults={"description": reason["description"]},
                    )
                    if created:
                        created_count += 1

                if created_count > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully created {created_count} new profile report reasons"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "No new profile report reasons were created (all already exist)"
                        )
                    )

        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f"Error loading profile report reasons: {str(e)}")
            )
            raise
