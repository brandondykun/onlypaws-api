# Backfill public_id for all existing rows in profile_app

import ulid
from django.db import migrations


def backfill_public_id(apps, schema_editor):
    PetType = apps.get_model('profile_app', 'PetType')
    Address = apps.get_model('profile_app', 'Address')
    Profile = apps.get_model('profile_app', 'Profile')
    ProfileImage = apps.get_model('profile_app', 'ProfileImage')
    ProfileImageScaled = apps.get_model('profile_app', 'ProfileImageScaled')

    for model in (PetType, Address, Profile, ProfileImage, ProfileImageScaled):
        for obj in model.objects.filter(public_id__isnull=True):
            obj.public_id = ulid.new()
            obj.save(update_fields=['public_id'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('profile_app', '0005_add_public_id'),
    ]

    operations = [
        migrations.RunPython(backfill_public_id, noop),
    ]
