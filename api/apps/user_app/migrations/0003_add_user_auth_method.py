# Generated manually for multi-provider auth support

from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("user_app", "0002_user_onboarding_fields"),
    ]

    operations = [
        migrations.CreateModel(
            name="AuthProvider",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                (
                    "provider",
                    models.CharField(
                        choices=[
                            ("email", "Email"),
                            ("google", "Google"),
                            ("apple", "Apple"),
                        ],
                        db_index=True,
                        max_length=32,
                    ),
                ),
                (
                    "external_id",
                    models.CharField(
                        help_text="Provider-specific identifier (e.g. email for email provider, OAuth sub for Google/Apple).",
                        max_length=255,
                    ),
                ),
                (
                    "token_data",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Provider-specific token data (e.g. OAuth refresh token). Not used for email.",
                    ),
                ),
                (
                    "metadata",
                    models.JSONField(
                        blank=True,
                        default=dict,
                        help_text="Additional metadata returned by the provider.",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "user",
                    models.ForeignKey(
                        on_delete=models.deletion.CASCADE,
                        related_name="auth_providers",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "ordering": ["provider"],
            },
        ),
        migrations.AddIndex(
            model_name="authprovider",
            index=models.Index(fields=["provider", "external_id"], name="user_app_authprovider_prov_ext_idx"),
        ),
        migrations.AddConstraint(
            model_name="authprovider",
            constraint=models.UniqueConstraint(
                fields=("provider", "external_id"),
                name="auth_provider_provider_external_id_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="authprovider",
            constraint=models.UniqueConstraint(
                fields=("user", "provider"),
                name="auth_provider_user_provider_uniq",
            ),
        ),
    ]
