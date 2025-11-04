import os
from django.core.management.base import BaseCommand
from django.core import serializers
from django.apps import apps


class Command(BaseCommand):
    help = "Create a fixture file for each model in the project."

    def handle(self, *args, **options):
        # Get current environment
        environment = os.environ.get("DJANGO_ENV")

        # Check if the environment is test or dev
        if environment != "test" and environment != "dev" and environment != "staging":
            self.stdout.write(
                self.style.ERROR(
                    "This command can only be run in a test, staging or local dev environment!"
                )
            )
            return

        # Create fixtures
        models = [
            "user",
            "profile",
            "regularprofile",
            "businessprofile",
            "address",
            "pendingemailchange",
            "profileimage",
            "post",
            "postimage",
            "like",
            "comment",
            "follow",
            "commentlike",
            "savedpost",
            "pettype",
            "reportreason",
            "postreport",
            "resetpasswordtoken",
            "verifyemailtoken",
            "feedback",
            "feedbackcomment",
            "notification",
            "appconfiguration",
        ]

        # default fixture path
        fixture_path = "fixtures/test"

        # override fixture path for dev environment
        if environment == "dev":
            fixture_path = "fixtures/dev"

        if environment == "staging":
            fixture_path = "fixtures/staging"

        # create fixtures for each model
        for model in apps.get_models():
            model_name = model.__name__.lower()
            if model_name in models:
                fixture_file = f"{fixture_path}/{model_name}.json"

                # Ensure the directory exists
                os.makedirs(os.path.dirname(fixture_file), exist_ok=True)

                # Check if file exists and fix permissions before opening
                if os.path.exists(fixture_file):
                    try:
                        # Try to make the file writable by the current user
                        os.chmod(fixture_file, 0o664)
                    except OSError as e:
                        self.stdout.write(
                            self.style.ERROR(
                                f"Cannot write to {fixture_file}. Permission denied. "
                                f"File is owned by a different user. Error: {e}"
                            )
                        )
                        continue

                try:
                    with open(fixture_file, "w") as f:
                        data = serializers.serialize("json", model.objects.all())
                        f.write(data)

                    # Set proper permissions for newly created files
                    os.chmod(fixture_file, 0o664)

                    self.stdout.write(
                        self.style.SUCCESS(f"Created fixture file: {fixture_file}")
                    )
                except (OSError, PermissionError) as e:
                    self.stdout.write(
                        self.style.ERROR(
                            f"Failed to create fixture file {fixture_file}: {e}. "
                            f"Try running the command as root or fix file permissions."
                        )
                    )
