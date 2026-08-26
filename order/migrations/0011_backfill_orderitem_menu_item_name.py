from django.db import migrations


def backfill_menu_item_name(apps, schema_editor):
    """
    Existing order items have no frozen name. The FK is PROTECT, so the live
    menu item is still there to copy the current name from - the best value
    available for orders placed before the field existed.
    """
    OrderItem = apps.get_model('order', 'OrderItem')
    to_update = []
    for item in OrderItem.objects.select_related('menu_item').filter(
            menu_item_name=''):
        item.menu_item_name = item.menu_item.name
        to_update.append(item)
    if to_update:
        OrderItem.objects.bulk_update(to_update, ['menu_item_name'])


def noop(apps, schema_editor):
    """Reversing just leaves the column populated; nothing to undo."""


class Migration(migrations.Migration):

    dependencies = [
        ('order', '0010_orderitem_menu_item_name'),
    ]

    operations = [
        migrations.RunPython(backfill_menu_item_name, noop),
    ]
