"""
Management command to ensure pgvector extension is installed.
"""
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = "Ensure the pgvector extension is installed in the database"

    def handle(self, *args, **options):
        with connection.cursor() as cursor:
            cursor.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            self.stdout.write(
                self.style.SUCCESS("Successfully ensured vector extension is installed")
            )
