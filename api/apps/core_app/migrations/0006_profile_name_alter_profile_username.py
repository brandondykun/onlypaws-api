# Generated by Django 5.1.1 on 2024-10-28 02:21

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core_app', '0005_alter_profile_user'),
    ]

    operations = [
        migrations.AddField(
            model_name='profile',
            name='name',
            field=models.CharField(default='', max_length=64),
        ),
        migrations.AlterField(
            model_name='profile',
            name='username',
            field=models.CharField(max_length=32, unique=True),
        ),
    ]
