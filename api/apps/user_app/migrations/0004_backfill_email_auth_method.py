# Data migration: backfill AuthProvider (email) for existing users

from django.db import migrations


def backfill_email_auth_provider(apps, schema_editor):
    User = apps.get_model("user_app", "User")
    AuthProvider = apps.get_model("user_app", "AuthProvider")
    provider_email = "email"

    for user in User.objects.all():
        AuthProvider.objects.get_or_create(
            user=user,
            provider=provider_email,
            defaults={"external_id": user.email, "metadata": {}},
        )


def noop_reverse(apps, schema_editor):
    """No-op reverse; we do not remove auth providers on rollback."""
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("user_app", "0003_add_user_auth_method"),
    ]

    operations = [
        migrations.RunPython(backfill_email_auth_provider, noop_reverse),
    ]
