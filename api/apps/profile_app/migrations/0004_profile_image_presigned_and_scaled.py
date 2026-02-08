# Generated manually for presigned URL profile image workflow and scaled variants

import django.db.models.deletion
from django.db import migrations, models
import apps.profile_app.models


class Migration(migrations.Migration):

    dependencies = [
        ('profile_app', '0003_profile_is_private'),
    ]

    operations = [
        migrations.AddField(
            model_name='profileimage',
            name='original_key',
            field=models.CharField(
                blank=True,
                help_text='S3 key for the original uploaded image (before processing)',
                max_length=500,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name='profileimage',
            name='processing_status',
            field=models.CharField(
                choices=[
                    ('PENDING_UPLOAD', 'Pending Upload'),
                    ('UPLOADED', 'Uploaded'),
                    ('PROCESSING', 'Processing'),
                    ('READY', 'Ready'),
                    ('FAILED', 'Failed'),
                ],
                default='READY',
                help_text='Image processing status',
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name='profileimage',
            name='image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=apps.profile_app.models.profile_image_path,
            ),
        ),
        migrations.CreateModel(
            name='ProfileImageScaled',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scale', models.CharField(
                    choices=[('small', 'Small'), ('medium', 'Medium')],
                    max_length=20,
                )),
                ('image', models.ImageField(upload_to=apps.profile_app.models.profile_scaled_path)),
                ('width', models.PositiveIntegerField(help_text='Width in pixels')),
                ('height', models.PositiveIntegerField(help_text='Height in pixels')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('profile_image', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scaled_images',
                    to='profile_app.profileimage',
                )),
            ],
            options={
                'unique_together': {('profile_image', 'scale')},
            },
        ),
        migrations.AddIndex(
            model_name='profileimagescaled',
            index=models.Index(fields=['profile_image', 'scale'], name='profile_app_profile_8a1b2c_idx'),
        ),
    ]
