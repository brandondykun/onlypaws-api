# Generated by Django 5.1.1 on 2025-01-30 05:29

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_app', '0019_user_is_email_verified_verifyemailtoken'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='contains_ai',
            field=models.BooleanField(blank=True, default=False),
        ),
    ]
