import django.db.models.deletion
from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemconfiguration',
            name='hero_image',
            field=models.ImageField(
                blank=True,
                help_text='Upload a custom hero background image for the landing page',
                null=True,
                upload_to='hero/',
            ),
        ),
        migrations.AddField(
            model_name='systemconfiguration',
            name='hero_image_url',
            field=models.URLField(
                blank=True,
                help_text='External URL for hero image (overrides uploaded image if set)',
            ),
        ),
    ]
