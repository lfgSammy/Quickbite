from django.core import mail
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from users.models import PasswordResetOTP, User


class PasswordResetFlowTests(APITestCase):
    """
    The whole flow used to 500: PasswordResetOTP had never been migrated, and
    users/models.py imported datetime.timezone (which has no .now()) instead
    of django.utils.timezone.
    """

    def setUp(self):
        # Throttle state and reset tokens both live in the cache, and
        # LocMemCache persists between tests in a run.
        cache.clear()
        self.user = User.objects.create_user(
            username='chidi', email='Chidi@Example.com',
            password='OldPassw0rd', role='customer')

    def test_forgot_password_issues_an_otp_and_emails_it(self):
        response = self.client.post(
            reverse('forgot-password'),
            {'email': 'chidi@example.com'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        otp = PasswordResetOTP.objects.get(user=self.user)
        self.assertEqual(len(otp.code), 6)
        self.assertGreater(otp.expires_at, timezone.now())

        self.assertEqual(len(mail.outbox), 1)
        body = mail.outbox[0].body
        # The template used to be a plain string, so these interpolated
        # nowhere and the customer received a literal "{code}".
        self.assertIn(otp.code, body)
        self.assertIn('chidi', body)
        self.assertNotIn('{code}', body)
        self.assertNotIn('{user.username}', body)

    def test_unknown_email_is_indistinguishable_from_a_known_one(self):
        known = self.client.post(
            reverse('forgot-password'),
            {'email': 'chidi@example.com'}, format='json')
        cache.clear()
        unknown = self.client.post(
            reverse('forgot-password'),
            {'email': 'nobody@example.com'}, format='json')

        self.assertEqual(known.status_code, unknown.status_code)
        self.assertEqual(known.data, unknown.data)

    def test_full_reset_lets_the_user_log_in_with_the_new_password(self):
        self.client.post(
            reverse('forgot-password'),
            {'email': 'chidi@example.com'}, format='json')
        code = PasswordResetOTP.objects.get(user=self.user).code

        verify = self.client.post(
            reverse('verify-reset-otp'),
            {'email': 'chidi@example.com', 'code': code}, format='json')
        self.assertEqual(verify.status_code, status.HTTP_200_OK)

        reset = self.client.post(
            reverse('reset-password'),
            {'reset_token': verify.data['reset_token'],
             'new_password': 'BrandNewPass1',
             'confirm_password': 'BrandNewPass1'}, format='json')
        self.assertEqual(reset.status_code, status.HTTP_200_OK)

        login = self.client.post(
            reverse('login'),
            {'username': 'chidi', 'password': 'BrandNewPass1'}, format='json')
        self.assertEqual(login.status_code, status.HTTP_200_OK)
        self.assertIn('access', login.data)

    def test_an_otp_cannot_be_reused(self):
        self.client.post(
            reverse('forgot-password'),
            {'email': 'chidi@example.com'}, format='json')
        code = PasswordResetOTP.objects.get(user=self.user).code

        first = self.client.post(
            reverse('verify-reset-otp'),
            {'email': 'chidi@example.com', 'code': code}, format='json')
        self.assertEqual(first.status_code, status.HTTP_200_OK)

        second = self.client.post(
            reverse('verify-reset-otp'),
            {'email': 'chidi@example.com', 'code': code}, format='json')
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_otp_codes_are_always_six_digits(self):
        codes = {PasswordResetOTP.generate_codes() for _ in range(200)}
        for code in codes:
            self.assertEqual(len(code), 6)
            self.assertTrue(code.isdigit())


class ThrottleTests(APITestCase):
    def setUp(self):
        cache.clear()

    def test_login_is_rate_limited(self):
        codes = [
            self.client.post(
                reverse('login'),
                {'username': 'nope', 'password': 'wrong'}, format='json'
            ).status_code
            for _ in range(15)
        ]
        self.assertIn(status.HTTP_429_TOO_MANY_REQUESTS, codes)
