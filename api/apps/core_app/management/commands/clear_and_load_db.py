import os
from django.core.management.base import BaseCommand
from django.core.management import call_command

from apps.notifications_app.signals import (
    disconnect_notification_signals,
    reconnect_notification_signals,
)


class Command(BaseCommand):
    help = "Clears the database and loads data from fixtures."

    def handle(self, *args, **options):

        environment = os.environ.get("DJANGO_ENV")
        # Clear the database
        if environment != "dev" and environment != "staging" and environment != "e2e":
            self.stdout.write(
                self.style.ERROR(
                    "This command can only be run in a staging, e2e or local dev environment!"
                )
            )
            return
        call_command("flush", "--noinput")

        self.stdout.write(self.style.SUCCESS("Database cleared successfully!"))

        # Fixture files to load
        # The order of the files in this list is important, as some fixtures depend on others.
        fixture_files = [
            "pettype.json",
            "reportreason.json",
            "user.json",
            "authprovider.json",
            "profile.json",
            "regularprofile.json",
            "businessprofile.json",
            "address.json",
            "pendingemailchange.json",
            "profileimage.json",
            "post.json",
            "postimage.json",
            "like.json",
            "comment.json",
            "follow.json",
            "commentlike.json",
            "savedpost.json",
            "postreport.json",
            "resetpasswordtoken.json",
            "verifyemailtoken.json",
            "feedback.json",
            "feedbackcomment.json",
            "notification.json",
            "appconfiguration.json",
            "postimagetag.json",
            "announcement.json",
            "postimagescaled.json",
            "profileimagescaled.json",
            "termsofservice.json",
            "termsacceptance.json",
            "custombannedword.json",
            "whitelistedword.json",
            "pendingaccountdeletion.json",
            "postinteraction.json",
        ]

        path_prefix = "fixtures/e2e"

        if environment == "dev":
            path_prefix = "fixtures/dev"

        if environment == "staging":
            path_prefix = "fixtures/staging"

        fixture_paths = [
            f"{path_prefix}/{fixture_file}" for fixture_file in fixture_files
        ]

        disconnect_notification_signals()
        try:
            for fixture_path in fixture_paths:
                call_command("loaddata", fixture_path)
        finally:
            reconnect_notification_signals()

        self.stdout.write(self.style.SUCCESS("Database fixtures loaded successfully!"))
