from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from users.models import Notification
from django.contrib.auth import get_user_model

User = get_user_model()

@receiver(post_save, sender=Order)
def handle_order_notification(sender, instance, created, **kwargs):
    if created:
        kitchen_staff = User.objects.filter(role='kitchen')
        for staff in kitchen_staff:
            Notification.objects.create(
                user=staff,
                message=f'New order #{instance.id} received. '
                        f'Total: ₦{instance.total_amount}. '
                        f'Pickup: {instance.pickup_time.strftime("%I:%M %p")}'
            )
    else:
        if instance.status == 'paid':
            Notification.objects.create(
                user = instance.customer,
                message=f'Payment confirmed for Order #{instance.id}. '
                        f'Check your email for your QR code. '
                        f'Pickup time: {instance.pickup_time.strftime("%I:%M %p")}'
            )

        elif instance.status == 'preparing':
            Notification.objects.create(
                user = instance.customer,
                message=f'Your order #{instance.id} is ready for pickup! '
                        f'Please show your QR code at the outlet.'
            )

        elif instance.status == 'ready':
            Notification.objects.create(
                user = instance.customer,
                message=f'Your order #{instance.id} is ready for pickup! '
                        f'Please show your QR code at the outlet.'
            )

        elif instance.status == 'collected':
            Notification.objects.create(
                user = instance.customer,
                message = f'Order #{instance.id} collected. Enjoy your meal!'
            )

        elif instance.status == 'cancelled':
            Notification.objects.create(
                user=instance.customer,
                message=f'Your order #{instance.id} has been cancelled.'
            )
