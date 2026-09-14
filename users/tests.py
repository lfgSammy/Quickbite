from unittest.mock import MagicMock, patch

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


class GoogleOAuthTests(APITestCase):
    def setUp(self):
        cache.clear()

    def _google(self, token_json=None, user_info=None):
        token_resp = MagicMock()
        token_resp.json.return_value = token_json or {'access_token': 'tok'}
        info_resp = MagicMock()
        info_resp.json.return_value = user_info or {
            'email': 'Ngozi@Gmail.com', 'verified_email': True}
        return token_resp, info_resp

    @patch('users.views.http_requests.get')
    @patch('users.views.http_requests.post')
    def test_the_redirect_uri_reaches_google_under_its_real_name(
            self, mock_post, mock_get):
        mock_post.return_value, mock_get.return_value = self._google()

        response = self.client.post(
            reverse('google-oauth'),
            {'code': 'abc', 'redirect_url': 'https://quickbite.app/auth/google'},
            format='json')

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        sent = mock_post.call_args.kwargs['data']
        # Google only recognises `redirect_uri`. Sending `redirect_url` meant it
        # received no redirect URI and rejected every exchange.
        self.assertEqual(sent['redirect_uri'], 'https://quickbite.app/auth/google')
        self.assertNotIn('redirect_url', sent)

    @patch('users.views.http_requests.get')
    @patch('users.views.http_requests.post')
    def test_both_google_calls_have_a_timeout(self, mock_post, mock_get):
        mock_post.return_value, mock_get.return_value = self._google()

        self.client.post(reverse('google-oauth'), {'code': 'abc'}, format='json')

        self.assertIsNotNone(mock_post.call_args.kwargs.get('timeout'))
        self.assertIsNotNone(mock_get.call_args.kwargs.get('timeout'))

    @patch('users.views.http_requests.post')
    def test_google_being_unreachable_is_a_502_not_a_500(self, mock_post):
        import requests
        mock_post.side_effect = requests.ConnectionError('down')

        response = self.client.post(
            reverse('google-oauth'), {'code': 'abc'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_502_BAD_GATEWAY)

    @patch('users.views.http_requests.get')
    @patch('users.views.http_requests.post')
    def test_an_unverified_google_email_cannot_sign_into_an_account(
            self, mock_post, mock_get):
        User.objects.create_user(
            username='victim', email='victim@example.com',
            password='Passw0rdOK', role='customer')
        mock_post.return_value, mock_get.return_value = self._google(
            user_info={'email': 'victim@example.com', 'verified_email': False})

        response = self.client.post(
            reverse('google-oauth'), {'code': 'abc'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn('access', response.data)

    @patch('users.views.http_requests.get')
    @patch('users.views.http_requests.post')
    def test_a_rejected_code_is_a_400(self, mock_post, mock_get):
        mock_post.return_value, mock_get.return_value = self._google(
            token_json={'error': 'invalid_grant'})

        response = self.client.post(
            reverse('google-oauth'), {'code': 'stale'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        mock_get.assert_not_called()


class PhoneNumberUniquenessTests(APITestCase):
    def setUp(self):
        cache.clear()

    def register(self, username, email, phone=None):
        payload = {'username': username, 'email': email,
                   'password': 'Passw0rdOK'}
        if phone is not None:
            payload['phone_number'] = phone
        cache.clear()  # keep the register throttle out of the way
        return self.client.post(reverse('register'), payload, format='json')

    def test_a_phone_number_already_in_use_is_a_400_not_a_500(self):
        first = self.register('ada', 'ada@example.com', '08012345678')
        second = self.register('bola', 'bola@example.com', '08012345678')

        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('phone', second.data['error'].lower())
        self.assertFalse(User.objects.filter(username='bola').exists())

    def test_several_people_can_register_without_a_phone_number(self):
        # Blank numbers are stored as NULL, which the unique index permits
        # any number of times - an empty string would collide.
        self.assertEqual(self.register('c1', 'c1@example.com').status_code, 201)
        self.assertEqual(self.register('c2', 'c2@example.com', '').status_code, 201)

    def test_changing_your_phone_to_one_already_taken_is_a_400(self):
        User.objects.create_user(
            username='owner', email='owner@example.com',
            password='Passw0rdOK', phone_number='08099999999')
        user = User.objects.create_user(
            username='mover', email='mover@example.com', password='Passw0rdOK')
        self.client.force_authenticate(user)

        response = self.client.patch(
            reverse('profile'), {'phone_number': '08099999999'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
