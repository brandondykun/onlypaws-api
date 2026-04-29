from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("moderation_app", "0009_custombannedword_whitelistedword"),
    ]

    operations = [
        migrations.AddIndex(
            model_name="profilereport",
            index=models.Index(
                fields=["status", "profile"],
                name="modr_pr_status_profile_idx",
            ),
        ),
    ]
