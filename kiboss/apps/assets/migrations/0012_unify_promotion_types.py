"""
Data migration: Unify all promotion types to SPONSORED.
"""
from django.db import migrations


def unify_promotion_types(apps, schema_editor):
    PromotedListing = apps.get_model('assets', 'PromotedListing')
    PromotedListing.objects.exclude(promotion_type='SPONSORED').update(promotion_type='SPONSORED')


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('assets', '0011_promotedlisting'),
    ]

    operations = [
        # 1. Migrate existing data
        migrations.RunPython(unify_promotion_types, noop),
        # 2. Alter the field to use the new single-choice enum
        migrations.AlterField(
            model_name='promotedlisting',
            name='promotion_type',
            field=__import__('django.db.models', fromlist=['CharField']).CharField(
                choices=[('SPONSORED', 'Sponsored Listing')],
                max_length=30,
            ),
        ),
    ]
