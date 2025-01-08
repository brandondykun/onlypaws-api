import os
from django.core.management.base import BaseCommand
from django.core.management import call_command


class Command(BaseCommand):
    help = "Clears the database and loads data from fixtures."

    def handle(self, *args, **options):
        # Clear the database
        if os.environ.get("DJANGO_ENV") != "test":
            self.stdout.write(
                self.style.ERROR("This command can only be run in a test environment!")
            )
            return
        call_command("flush", "--noinput")

        self.stdout.write(self.style.SUCCESS("Database cleared successfully!"))

        # Load fixtures
        fixture_paths = [
            "fixtures/user.json",
            "fixtures/profile.json",
            "fixtures/profileimage.json",
            "fixtures/post.json",
            "fixtures/postimage.json",
            "fixtures/like.json",
            "fixtures/comment.json",
            "fixtures/follow.json",
            "fixtures/commentlike.json",
            "fixtures/pettype.json",
            "fixtures/savedpost.json",
            "fixtures/reportreason.json",
            "fixtures/postreport.json",
        ]
        for fixture_path in fixture_paths:
            call_command("loaddata", fixture_path)

        self.stdout.write(self.style.SUCCESS("Database fixtures loaded successfully!"))
