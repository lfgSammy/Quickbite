from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from users.models import Notification

@receiver(post_save, sender=Order)
def notify_on_order_status_change(sender, instance,created, **kwargs):
    if created:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        kitchen_staff = User.objects.filter(role= 'kitchen')
        for staff in kitchen_staff:
            Notification.objects.create(
                user=staff,
                message = f'New order #{instance.id} received. '
                          f'Pickup time: {instance.pickup_time}'
            )             

    else:
        if instance.status == 'preparing':
            Notification.objects.create(
                user=instance.customer,
                message=f'Your order #{instance.id} is being prepared!'
            )

        elif instance.status == 'preparing':
            Notification.objects.create(
                user = instance.customer,
                message= f'Your order #{instance.id} is ready for pickup!'
                         f'Please show your QR code at the outlet'
            )

        elif instance.status == 'collected':
            Notification.objects.create(
                user=instance.customer,
                message=f'Order #{instance.id} collected. Enjoy your meal!'
            )

        elif instance.status == 'cancelled':
            Notification.objects.create(
                user=instance.customer,
                message=f'Your order #{instance.id} has been cancelled.'
            )