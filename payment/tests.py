from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from order.models import Order
from payment.models import Payment
from users.models import Notification, User


def paystack_success(amount_kobo, reference='ref_1'):
    return {
        'status': True,
        'data': {'status': 'success', 'amount': amount_kobo,
                 'reference': reference},
    }


class VerifyPaymentTests(APITestCase):
    def setUp(self):
        self.owner = User.objects.create_user(
            username='owner', email='owner@example.com',
            password='Passw0rdy', role='customer')
        self.stranger = User.objects.create_user(
            username='stranger', email='stranger@example.com',
            password='Passw0rdy', role='customer')

        self.order = Order.objects.create(
            customer=self.owner, total_amount=Decimal('4000.00'),
            pickup_time=timezone.now() + timedelta(hours=2), status='pending')
        self.payment = Payment.objects.create(
            order=self.order, paystack_reference='ref_1',
            amount=Decimal('4000.00'), status='pending')

    def _verify(self, user, reference='ref_1'):
        self.client.force_authenticate(user)
        return self.client.post(
            reverse('payment-verify'), {'reference': reference}, format='json')

    @patch('payment.views.send_qr_code_email')
    @patch('payment.views.paystack_get')
    def test_owner_can_verify_their_payment(self, mock_get, _mail):
        mock_get.return_value = paystack_success(400000)

        response = self._verify(self.owner)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.order.refresh_from_db()
        self.payment.refresh_from_db()
        self.assertEqual(self.order.status, 'paid')
        self.assertEqual(self.payment.status, 'success')

    @patch('payment.views.paystack_get')
    def test_another_user_cannot_verify_someone_elses_payment(self, mock_get):
        mock_get.return_value = paystack_success(400000)

        response = self._verify(self.stranger)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')
        # Paystack should not even have been called for someone else's ref.
        mock_get.assert_not_called()

    @patch('payment.views.send_qr_code_email')
    @patch('payment.views.paystack_get')
    def test_an_underpaid_charge_does_not_mark_the_order_paid(
            self, mock_get, _mail):
        # 1000 naira paid against a 4000 naira order.
        mock_get.return_value = paystack_success(100000)

        response = self._verify(self.owner)

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')

    @patch('payment.views.send_qr_code_email')
    @patch('payment.views.paystack_get')
    def test_verifying_twice_is_idempotent(self, mock_get, mock_mail):
        mock_get.return_value = paystack_success(400000)

        first = self._verify(self.owner)
        second = self._verify(self.owner)

        self.assertEqual(first.status_code, status.HTTP_200_OK)
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data['message'], 'Payment already verified')
        # The QR email must not go out a second time.
        self.assertEqual(mock_mail.call_count, 1)

    @patch('payment.views.send_qr_code_email')
    @patch('payment.views.paystack_get')
    def test_paid_order_notifies_the_customer_exactly_once(
            self, mock_get, _mail):
        mock_get.return_value = paystack_success(400000)

        self._verify(self.owner)

        confirmations = Notification.objects.filter(
            user=self.owner, message__icontains='Payment confirmed')
        # The Order post_save signal owns this message; the payment view used
        # to create a second copy of it.
        self.assertEqual(confirmations.count(), 1)

    @patch('payment.views.paystack_get')
    def test_provider_outage_returns_502_not_a_500(self, mock_get):
        mock_get.return_value = None

        response = self._verify(self.owner)

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')


class DuplicateChargeTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='dup', email='dup@example.com',
            password='Passw0rdy', role='customer')
        self.order = Order.objects.create(
            customer=self.user, total_amount=Decimal('4000.00'),
            pickup_time=timezone.now() + timedelta(hours=2), status='paid')
        self.second_attempt = Payment.objects.create(
            order=self.order, paystack_reference='ref_2',
            amount=Decimal('4000.00'), status='pending')

    @patch('payment.views.send_qr_code_email')
    @patch('payment.views.paystack_get')
    def test_a_second_real_charge_is_flagged_for_refund(self, mock_get, mail):
        mock_get.return_value = paystack_success(400000, 'ref_2')
        self.client.force_authenticate(self.user)

        response = self.client.post(
            reverse('payment-verify'), {'reference': 'ref_2'}, format='json')

        self.assertIn('warning', response.data)
        self.second_attempt.refresh_from_db()
        self.assertEqual(self.second_attempt.status, 'success')
        self.assertTrue(Notification.objects.filter(
            user=self.user, message__icontains='duplicate payment').exists())
        # No second QR code for a charge that will be refunded.
        mail.assert_not_called()


class WebhookTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='hook', email='hook@example.com',
            password='Passw0rdy', role='customer')
        self.order = Order.objects.create(
            customer=self.user, total_amount=Decimal('4000.00'),
            pickup_time=timezone.now() + timedelta(hours=2), status='pending')
        Payment.objects.create(
            order=self.order, paystack_reference='ref_3',
            amount=Decimal('4000.00'), status='pending')

    def test_an_unsigned_webhook_is_rejected(self):
        response = self.client.post(
            reverse('payment-webhook'),
            {'event': 'charge.success', 'data': {'reference': 'ref_3'}},
            format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.order.refresh_from_db()
        self.assertEqual(self.order.status, 'pending')
