# Generated manually on 2025-11-18

import pgvector.django.vector
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('posts_app', '0002_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='post',
            name='combined_embedding',
            field=pgvector.django.vector.VectorField(blank=True, dimensions=512, help_text='Combined embedding from images and caption', null=True),
        ),
        migrations.AddField(
            model_name='post',
            name='combined_embedding_generated_at',
            field=models.DateTimeField(blank=True, help_text='When the combined embedding was generated', null=True),
        ),
        migrations.AddField(
            model_name='post',
            name='combined_embedding_model',
            field=models.CharField(default='clip-vit-base-patch32', help_text='Model used to generate the combined embedding', max_length=100),
        ),
    ]

