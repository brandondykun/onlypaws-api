# Generated manually for presigned URL upload workflow

from django.db import migrations, models
import django.db.models.deletion
import apps.posts_app.models


class Migration(migrations.Migration):

    dependencies = [
        ('posts_app', '0006_post_aspect_ratio'),
    ]

    operations = [
        # Add status field to Post model
        migrations.AddField(
            model_name='post',
            name='status',
            field=models.CharField(
                choices=[
                    ('PENDING_UPLOAD', 'Pending Upload'),
                    ('PROCESSING', 'Processing'),
                    ('READY', 'Ready'),
                    ('FAILED', 'Failed'),
                ],
                default='READY',
                help_text='Post lifecycle status',
                max_length=20,
            ),
        ),
        # Add processing_status field to PostImage model
        migrations.AddField(
            model_name='postimage',
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
        # Add original_key field to PostImage model
        migrations.AddField(
            model_name='postimage',
            name='original_key',
            field=models.CharField(
                blank=True,
                help_text='S3 key for the original uploaded image (before processing)',
                max_length=500,
                null=True,
            ),
        ),
        # Allow PostImage.image to be nullable for placeholder images
        migrations.AlterField(
            model_name='postimage',
            name='image',
            field=models.ImageField(
                blank=True,
                null=True,
                upload_to=apps.posts_app.models.post_image_path,
            ),
        ),
        # Create PostImageScaled model
        migrations.CreateModel(
            name='PostImageScaled',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('scale', models.CharField(
                    choices=[
                        ('thumbnail', 'Thumbnail'),
                        ('small', 'Small'),
                        ('medium', 'Medium'),
                        ('large', 'Large'),
                    ],
                    max_length=20,
                )),
                ('image', models.ImageField(upload_to=apps.posts_app.models.post_image_scaled_path)),
                ('width', models.PositiveIntegerField(help_text='Width in pixels')),
                ('height', models.PositiveIntegerField(help_text='Height in pixels')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('post_image', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='scaled_images',
                    to='posts_app.postimage',
                )),
            ],
            options={
                'unique_together': {('post_image', 'scale')},
            },
        ),
        # Add index for PostImageScaled
        migrations.AddIndex(
            model_name='postimagescaled',
            index=models.Index(fields=['post_image', 'scale'], name='posts_app_p_post_im_7c1a8b_idx'),
        ),
    ]
