# Generated manually for onboarding tracking

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('user_app', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='user',
            name='regular_profile_onboarding_completed',
            field=models.BooleanField(default=False, help_text='Whether the user has completed onboarding for RegularProfile type'),
        ),
        migrations.AddField(
            model_name='user',
            name='business_profile_onboarding_completed',
            field=models.BooleanField(default=False, help_text='Whether the user has completed onboarding for BusinessProfile type'),
        ),
    ]
