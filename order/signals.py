from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Order
from users.models import Notification
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings

User = get_user_model()


@receiver(post_save, sender=Order)
def handle_order_notifications(sender, instance, created, **kwargs):
    pickup_time = instance.pickup_time
    pickup_str = (timezone.localtime(pickup_time).strftime("%I:%M %p")
                  if pickup_time else 'N/A')

    if created:
        kitchen_staff = User.objects.filter(role='kitchen')
        for staff in kitchen_staff:
            Notification.objects.create(
                user=staff,
                message=f'New order #{instance.id} received. '
                        f'Total: ₦{instance.total_amount}. '
                        f'Pickup: {pickup_str}'
            )
    else:
        if instance.status == 'paid':
            Notification.objects.create(
                user=instance.customer,
                message=f'Payment confirmed for Order #{instance.id}. '
                        f'Check your email for your QR code. '
                        f'Pickup time: {pickup_str}'
            )
        elif instance.status == 'preparing':
            Notification.objects.create(
                user=instance.customer,
                message=f'Your order #{instance.id} is now being prepared!'
            )
        elif instance.status == 'ready':
            send_mail(
                subject='Your QuickBite order is ready!',
                message=f'''Hi {instance.customer.username}, your order #{instance.id} 
                    is ready for pickup. Show your QR code at the outlet.''',
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[instance.customer.email],
                fail_silently=True,
            )
            
            Notification.objects.create(
                user=instance.customer,
                message=f'Your order #{instance.id} is ready for pickup! '
                        f'Please show your QR code at the outlet.'
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