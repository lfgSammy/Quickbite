import uuid

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def populate_tokens(apps, schema_editor):
    """
    Give every existing cart its own token.

    Written by hand rather than generated: adding a unique column with a single
    default would hand every existing row the same value and break the unique
    constraint the moment it is applied.
    """
    Cart = apps.get_model('order', 'Cart')
    for cart in Cart.objects.filter(token__isnull=True):
        cart.token = uuid.uuid4()
        cart.save(update_fields=['token'])


def noop(apps, schema_editor):
    """Nothing to undo - the column goes away when this is reversed."""


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        ('order', '0011_backfill_orderitem_menu_item_name'),
    ]

    operations = [
        # 1. add it nullable and non-unique, so existing rows are undisturbed
        migrations.AddField(
            model_name='cart',
            name='token',
            field=models.UUIDField(null=True, editable=False),
        ),
        # 2. fill in a distinct value per row
        migrations.RunPython(populate_tokens, noop),
        # 3. now the unique constraint can hold
        migrations.AlterField(
            model_name='cart',
            name='token',
            field=models.UUIDField(
                default=uuid.uuid4, editable=False, unique=True),
        ),
        # 4. a cart no longer needs an owner
        migrations.AlterField(
            model_name='cart',
            name='customer',
            field=models.OneToOneField(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='cart',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
    ]
