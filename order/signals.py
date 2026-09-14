import logging
import threading

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.db import transaction
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Order
from users.models import Notification

User = get_user_model()
logger = logging.getLogger(__name__)


@receiver(pre_save, sender=Order)
def remember_previous_status(sender, instance, **kwargs):
    """
    Note the status as it stands in the database before this save.

    post_save alone cannot tell a status *change* from any other save, so
    every save of a paid order re-sent "payment confirmed" - including an
    admin editing an unrelated field. Comparing against the stored value
    means notifications fire once, on the transition that earns them.
    """
    if instance.pk is None:
        instance._previous_status = None
        return
    instance._previous_status = (
        sender.objects.filter(pk=instance.pk)
        .values_list('status', flat=True)
        .first()
    )


def send_ready_email(username, email, order_id):
    """Runs on a background thread, so it must not touch the database."""
    try:
        send_mail(
            subject='Your QuickBite order is ready!',
            message=(
                f'Hi {username}, your order #{order_id} is ready for pickup. '
                f'Show your QR code at the outlet.'
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            fail_silently=False,
        )
    except Exception:
        logger.exception('Failed to send ready email for order %s', order_id)


@receiver(post_save, sender=Order)
def handle_order_notifications(sender, instance, created, **kwargs):
    previous = getattr(instance, '_previous_status', None)
    if instance.status == previous:
        return

    pickup_time = instance.pickup_time
    pickup_str = (timezone.localtime(pickup_time).strftime("%I:%M %p")
                  if pickup_time else 'N/A')

    if instance.status == 'paid':
        # The kitchen hears about an order when it is paid for - the moment it
        # becomes food to cook. It used to be told on creation, while still
        # unpaid, so staff were pinged about abandoned checkouts and heard
        # nothing when the money actually arrived.
        kitchen_staff = User.objects.filter(role='kitchen')
        Notification.objects.bulk_create([
            Notification(
                user=staff,
                message=f'New paid order #{instance.id}. '
                        f'Total: ₦{instance.total_amount}. '
                        f'Pickup: {pickup_str}'
            )
            for staff in kitchen_staff
        ])
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
        Notification.objects.create(
            user=instance.customer,
            message=f'Your order #{instance.id} is ready for pickup! '
                    f'Please show your QR code at the outlet.'
        )

        # This used to call send_mail() right here, inside the kitchen's
        # request - so a slow mail server froze the kitchen screen every time
        # staff marked an order ready. Now it runs after the save commits, on
        # a background thread, the same way the payment QR email does. The
        # values are read here so the thread never needs the database.
        customer = instance.customer
        args = (customer.username, customer.email, instance.id)
        transaction.on_commit(
            lambda: threading.Thread(
                target=send_ready_email, args=args, daemon=True).start()
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
