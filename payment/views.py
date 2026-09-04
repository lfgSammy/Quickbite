import hashlib
import hmac
import io
import logging
import threading
import uuid

import qrcode
import requests
from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Payment
from .serializers import (PaymentSerializer,
                          InitializePaymentRequestSerializer,
                          InitializePaymentResponseSerializer,
                          VerifyPaymentRequestSerializer,
                          VerifyPaymentResponseSerializer,
                          WebhookAckSerializer)
from order.models import Order
from users.models import Notification

logger = logging.getLogger(__name__)

PAYSTACK_TIMEOUT = 15  # seconds; without this a hung Paystack hangs a worker

DUPLICATE_MESSAGE = (
    'We detected a duplicate payment for Order #{order_id}. This charge will '
    "be refunded - contact support if you don't hear from us within 24 hours."
)


def generate_qr_code(qr_data):
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(str(qr_data))
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    buffer.seek(0)
    return buffer


def send_qr_code_email(user, order):
    try:
        qr_buffer = generate_qr_code(order.qr_code)

        email = EmailMessage(
            subject=f'QuickBite - Order #{order.id} Confirmed!',
            body=f'''
Hi {user.username},

Your order has been confirmed and payment received!

Order Details:
- Order ID: #{order.id}
- Total: N{order.total_amount}
- Pickup Time: {order.pickup_time.strftime('%B %d, %Y at %I:%M %p')}

Your QR code is attached to this email.
Show it at the outlet when collecting your order.

Thank you for choosing QuickBite!
            ''',
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=[user.email]
        )
        email.attach(
            f'order_{order.id}_qrcode.png',
            qr_buffer.getvalue(),
            'image/png'
        )
        email.send(fail_silently=False)
        logger.info('QR code email sent for order %s', order.id)
    except Exception:
        logger.exception('Failed to send QR code email for order %s', order.id)


def paystack_get(url):
    """Call Paystack and return its parsed body, or None if unusable."""
    try:
        response = requests.get(
            url,
            headers={'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'},
            timeout=PAYSTACK_TIMEOUT,
        )
        return response.json()
    except (requests.RequestException, ValueError):
        logger.exception('Paystack request failed: %s', url)
        return None


def settle_payment(payment_id, paystack_amount_kobo):
    """
    Mark a payment successful and move its order to `paid`.

    Both the customer's verify call and Paystack's webhook land here, and they
    can arrive at the same moment - so the payment and its order are locked and
    re-read inside one transaction. Without that, both callers could observe a
    pending order and each run the success path, double-sending the QR email.

    Returns one of: 'settled', 'already_settled', 'duplicate', 'amount_mismatch'.
    """
    with transaction.atomic():
        payment = Payment.objects.select_for_update().select_related(
            'order__customer').get(pk=payment_id)
        order = Order.objects.select_for_update().get(pk=payment.order_id)

        if payment.status == 'success':
            return 'already_settled', payment, order

        # Paystack works in kobo. If what was actually charged doesn't match
        # what this order costs, do not mark the order paid off it.
        expected_kobo = int(payment.amount * 100)
        if paystack_amount_kobo is not None and \
                int(paystack_amount_kobo) != expected_kobo:
            logger.error(
                'Payment %s amount mismatch: charged %s kobo, expected %s kobo',
                payment.paystack_reference, paystack_amount_kobo, expected_kobo)
            return 'amount_mismatch', payment, order

        # The order was already paid by a DIFFERENT attempt. Paystack genuinely
        # processed a second real charge - record it truthfully, but don't
        # pretend nothing is wrong. Flag it so it gets refunded.
        if order.status != 'pending':
            payment.status = 'success'
            payment.verified_at = timezone.now()
            payment.save(update_fields=['status', 'verified_at'])

            Notification.objects.create(
                user=order.customer,
                message=DUPLICATE_MESSAGE.format(order_id=order.id),
            )
            return 'duplicate', payment, order

        payment.status = 'success'
        payment.verified_at = timezone.now()
        payment.save(update_fields=['status', 'verified_at'])

        order.status = 'paid'
        # The post_save signal on Order raises the "Payment confirmed"
        # notification for this transition. Creating one here as well - which
        # both the old verify view and the old webhook did - sent the customer
        # the same notification twice.
        order.save(update_fields=['status', 'updated_at'])

    # Outside the transaction: the email is slow and must never hold a row
    # lock, nor delay the response the customer is waiting on.
    threading.Thread(
        target=send_qr_code_email, args=(order.customer, order), daemon=True
    ).start()

    return 'settled', payment, order


class InitializePaymentView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InitializePaymentResponseSerializer

    @extend_schema(request=InitializePaymentRequestSerializer)
    def post(self, request):
        order_id = request.data.get('order_id')

        order = Order.objects.filter(
            id=order_id, customer=request.user).first()
        if not order:
            return Response({'error': 'No order found'},
                            status=status.HTTP_404_NOT_FOUND)
        if order.status != 'pending':
            return Response({'error': 'Order is not pending payment'},
                            status=status.HTTP_400_BAD_REQUEST)

        data = {
            'email': request.user.email,
            'amount': int(order.total_amount * 100),  # paystack uses kobo
            # A fresh unique suffix per attempt - Paystack rejects a second
            # initialize call that reuses a reference, which previously broke
            # "Pay now" retries on a still-pending order.
            'reference': f'order_{order.id}_{uuid.uuid4().hex[:10]}',
            'callback_url': f'{settings.FRONTEND_URL}/payment/callback',
            'metadata': {
                'order_id': order.id,
                'customer': request.user.username,
            },
        }

        try:
            response = requests.post(
                'https://api.paystack.co/transaction/initialize',
                json=data,
                headers={
                    'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}',
                    'Content-Type': 'application/json',
                },
                timeout=PAYSTACK_TIMEOUT,
            )
            response_data = response.json()
        except (requests.RequestException, ValueError):
            logger.exception('Paystack initialize failed for order %s', order.id)
            return Response(
                {'error': 'Could not reach the payment provider. Try again.'},
                status=status.HTTP_502_BAD_GATEWAY)

        if not response_data.get('status'):
            return Response({'error': 'Payment initialization failed'},
                            status=status.HTTP_400_BAD_REQUEST)

        Payment.objects.create(
            order=order,
            paystack_reference=response_data['data']['reference'],
            amount=order.total_amount,
            status='pending',
        )

        return Response({
            'payment_url': response_data['data']['authorization_url'],
            'reference': response_data['data']['reference'],
        })


class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = VerifyPaymentResponseSerializer

    @extend_schema(request=VerifyPaymentRequestSerializer)
    def post(self, request):
        reference = request.data.get('reference')
        if not reference:
            return Response({'error': 'Reference is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        # Scoped to the caller's own orders. This used to look the reference up
        # globally, so any authenticated user could drive verification on
        # somebody else's payment.
        payment = Payment.objects.filter(
            paystack_reference=reference,
            order__customer=request.user,
        ).select_related('order').first()
        if not payment:
            return Response({'error': 'Payment record not found'},
                            status=status.HTTP_404_NOT_FOUND)

        response_data = paystack_get(
            f'https://api.paystack.co/transaction/verify/{reference}')
        if response_data is None:
            return Response(
                {'error': 'Could not reach the payment provider. Try again.'},
                status=status.HTTP_502_BAD_GATEWAY)

        if not response_data.get('status'):
            return Response({'error': 'Verification failed'},
                            status=status.HTTP_400_BAD_REQUEST)

        paystack_data = response_data['data']

        if paystack_data.get('status') != 'success':
            payment.status = 'failed'
            payment.save(update_fields=['status'])
            return Response({'error': 'Payment was not successful'},
                            status=status.HTTP_400_BAD_REQUEST)

        outcome, payment, order = settle_payment(
            payment.pk, paystack_data.get('amount'))

        if outcome == 'amount_mismatch':
            return Response(
                {'error': 'The amount paid does not match this order. '
                          'Our team has been notified.'},
                status=status.HTTP_400_BAD_REQUEST)

        if outcome == 'duplicate':
            return Response({
                'warning': 'This order was already paid by an earlier attempt. '
                           'Your payment went through and will be refunded.',
                'order_id': order.id,
            })

        message = ('Payment already verified' if outcome == 'already_settled'
                   else 'Payment verified successfully')
        return Response({
            'message': message,
            'payment': PaymentSerializer(payment).data,
            'qr_code': str(order.qr_code),
            'order_id': order.id,
        })


class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []
    serializer_class = WebhookAckSerializer

    def post(self, request):
        paystack_signature = request.headers.get('x-paystack-signature')
        computed_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            request.body,
            hashlib.sha512,
        ).hexdigest()

        # Constant-time compare so the signature can't be recovered by timing.
        if not paystack_signature or not hmac.compare_digest(
                paystack_signature, computed_signature):
            return Response({'error': 'Invalid signature'},
                            status=status.HTTP_400_BAD_REQUEST)

        event = request.data.get('event')
        data = request.data.get('data', {})

        if event == 'charge.success':
            payment = Payment.objects.filter(
                paystack_reference=data.get('reference')).first()
            if payment:
                # Same settlement path as the customer-facing verify call, so
                # whichever arrives first wins and the other is a no-op.
                settle_payment(payment.pk, data.get('amount'))

        return Response({'status': 'ok'})
