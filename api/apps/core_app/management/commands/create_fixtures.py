from django.core.management.base import BaseCommand
from django.core import serializers
from django.apps import apps


class Command(BaseCommand):
    help = "Create a fixture file for each model in the project."

    def handle(self, *args, **options):
        # Create fixtures
        models = [
            "user",
            "profile",
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
        ]
        for model in apps.get_models():
            model_name = model.__name__.lower()
            if model_name in models:
                fixture_file = f"fixtures/{model_name}.json"
                with open(fixture_file, "w") as f:
                    data = serializers.serialize("json", model.objects.all())
                    f.write(data)
                self.stdout.write(
                    self.style.SUCCESS(f"Created fixture file: {fixture_file}")
                )
