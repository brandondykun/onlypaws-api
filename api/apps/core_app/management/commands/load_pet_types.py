from django.core.management.base import BaseCommand
from django.db import transaction
from apps.core_app.models import PetType  # Replace with your actual app name


class Command(BaseCommand):
    help = "Loads initial pet types into the database"

    def handle(self, *args, **kwargs):
        # Define your preset pet types
        pet_types = [
            {"name": "Dog"},
            {"name": "Cat"},
            {"name": "Fish"},
            {"name": "Bird"},
            {"name": "Rabbit"},
            {"name": "Hamster"},
            {"name": "Guinea Pig"},
            {"name": "Turtle"},
            {"name": "Ferret"},
            {"name": "Duck"},
            {"name": "Pig"},
            {"name": "Chicken"},
            {"name": "Other"},
        ]

        try:
            with transaction.atomic():
                # Keep track of how many pet types we create
                created_count = 0

                for pet_type in pet_types:
                    # Only create if it doesn't already exist
                    _, created = PetType.objects.get_or_create(name=pet_type["name"])
                    if created:
                        created_count += 1

                # Print success message
                if created_count > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully created {created_count} new pet types"
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(
                            "No new pet types were created (all already exist)"
                        )
                    )

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error loading pet types: {str(e)}"))
            raise
