"""
Django management command to toggle maintenance mode.

Usage:
    python manage.py maintenance on [--message "Custom message"] [--end-time "2024-01-15T14:00:00"]
    python manage.py maintenance off
    python manage.py maintenance status
"""

import json
from pathlib import Path

from django.core.management.base import BaseCommand

# Same location as middleware uses
MAINTENANCE_FLAG_FILE = Path('/tmp/maintenance_mode.json')


class Command(BaseCommand):
    """Django command to toggle maintenance mode."""

    help = "Toggle maintenance mode on/off or check current status"

    def add_arguments(self, parser):
        parser.add_argument(
            "action",
            type=str,
            choices=["on", "off", "status"],
            help="Action to perform: on, off, or status",
        )
        parser.add_argument(
            "--message",
            "-m",
            type=str,
            default="The system is currently undergoing maintenance. Please try again later.",
            help="Custom maintenance message to display",
        )
        parser.add_argument(
            "--end-time",
            "-e",
            type=str,
            default=None,
            help="Estimated end time in ISO format (e.g., 2024-01-15T14:00:00)",
        )
        parser.add_argument(
            "--allow-admin",
            "-a",
            action="store_true",
            default=False,
            help="Allow admin users to access the site during maintenance",
        )

    def handle(self, *args, **options):
        """Entry point for command."""
        action = options["action"]

        if action == "status":
            self._show_status()
        elif action == "on":
            self._enable_maintenance(
                message=options["message"],
                end_time=options["end_time"],
                allow_admin=options["allow_admin"],
            )
        elif action == "off":
            self._disable_maintenance()

    def _show_status(self):
        """Display the current maintenance mode status."""
        if MAINTENANCE_FLAG_FILE.exists():
            try:
                data = json.loads(MAINTENANCE_FLAG_FILE.read_text())
                self.stdout.write(self.style.WARNING("Maintenance mode: ENABLED"))
                self.stdout.write(f"  Flag file: {MAINTENANCE_FLAG_FILE}")
                if data.get('message'):
                    self.stdout.write(f"  Message: {data['message']}")
                if data.get('end_time'):
                    self.stdout.write(f"  Estimated end time: {data['end_time']}")
                if data.get('allow_admin'):
                    self.stdout.write("  Admin access: ALLOWED")
                else:
                    self.stdout.write("  Admin access: BLOCKED")
                return
            except (json.JSONDecodeError, IOError) as e:
                self.stdout.write(
                    self.style.ERROR(f"Error reading flag file: {e}")
                )

        self.stdout.write(self.style.SUCCESS("Maintenance mode: DISABLED"))
        self.stdout.write("  System is operational")

    def _enable_maintenance(self, message, end_time, allow_admin):
        """Enable maintenance mode by creating a flag file."""
        data = {
            'enabled': True,
            'message': message,
            'end_time': end_time,
            'allow_admin': allow_admin,
        }

        try:
            MAINTENANCE_FLAG_FILE.write_text(json.dumps(data, indent=2))
            self.stdout.write(
                self.style.SUCCESS(f"Maintenance mode ENABLED")
            )
            self.stdout.write(f"  Flag file: {MAINTENANCE_FLAG_FILE}")
            self.stdout.write(f"  Message: {message}")
            if end_time:
                self.stdout.write(f"  Estimated end time: {end_time}")
            if allow_admin:
                self.stdout.write("  Admin access: ALLOWED")
        except IOError as e:
            self.stdout.write(
                self.style.ERROR(f"Failed to create maintenance flag: {e}")
            )

    def _disable_maintenance(self):
        """Disable maintenance mode by removing the flag file."""
        if MAINTENANCE_FLAG_FILE.exists():
            try:
                MAINTENANCE_FLAG_FILE.unlink()
                self.stdout.write(
                    self.style.SUCCESS("Maintenance mode DISABLED")
                )
                self.stdout.write("  System is now operational")
            except IOError as e:
                self.stdout.write(
                    self.style.ERROR(f"Failed to remove maintenance flag: {e}")
                )
        else:
            self.stdout.write(
                self.style.SUCCESS("Maintenance mode already DISABLED")
            )
            self.stdout.write("  System is operational")
