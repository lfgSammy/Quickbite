from decimal import Decimal

from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from menu.models import MenuItem
from users.models import User


class PermissionTests(APITestCase):
    """
    The inline `if not request.user.is_admin` guards were replaced with
    permission classes. These check the doors are still locked.
    """

    def setUp(self):
        self.customer = User.objects.create_user(
            username='cust', email='cust@example.com',
            password='Passw0rdy', role='customer')
        self.kitchen = User.objects.create_user(
            username='chef', email='chef@example.com',
            password='Passw0rdy', role='kitchen')
        self.admin = User.objects.create_user(
            username='boss', email='boss@example.com',
            password='Passw0rdy', role='admin')
        self.item = MenuItem.objects.create(name='Jollof', item_type='rice')

    # ---- menu: public read, admin write ----

    def test_menu_is_readable_without_an_account(self):
        response = self.client.get(reverse('menu-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_customer_cannot_create_a_menu_item(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            reverse('menu-list'), {'name': 'Sneaky', 'item_type': 'rice'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kitchen_cannot_create_a_menu_item(self):
        self.client.force_authenticate(self.kitchen)
        response = self.client.post(
            reverse('menu-list'), {'name': 'Sneaky', 'item_type': 'rice'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_create_a_menu_item(self):
        self.client.force_authenticate(self.admin)
        response = self.client.post(
            reverse('menu-list'), {'name': 'New Dish', 'item_type': 'rice'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_anonymous_cannot_delete_a_menu_item(self):
        response = self.client.delete(
            reverse('menu-detail', args=[self.item.id]))
        self.assertIn(response.status_code,
                      (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))
        self.assertTrue(MenuItem.objects.filter(id=self.item.id).exists())

    # ---- admin-only areas ----

    def test_customer_cannot_list_users(self):
        self.client.force_authenticate(self.customer)
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_admin_can_list_users(self):
        self.client.force_authenticate(self.admin)
        response = self.client.get(reverse('user-list'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_customer_cannot_assign_roles(self):
        self.client.force_authenticate(self.customer)
        response = self.client.patch(
            reverse('assign-role', args=[self.customer.id]),
            {'role': 'admin'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.customer.refresh_from_db()
        self.assertEqual(self.customer.role, 'customer')

    def test_kitchen_cannot_see_the_admin_dashboard(self):
        self.client.force_authenticate(self.kitchen)
        response = self.client.get(reverse('admin-dashboard'))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_customer_cannot_set_operating_hours(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            reverse('operating-hours'),
            {'day': 0, 'open_time': '08:00', 'close_time': '22:00'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_operating_hours_stay_publicly_readable(self):
        response = self.client.get(reverse('operating-hours'))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    # ---- kitchen areas ----

    def test_customer_cannot_verify_a_qr_code(self):
        self.client.force_authenticate(self.customer)
        response = self.client.post(
            reverse('verify-qr'), {'qr_code': 'anything'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_kitchen_can_reach_qr_verification(self):
        self.client.force_authenticate(self.kitchen)
        response = self.client.post(
            reverse('verify-qr'), {'qr_code': 'not-a-real-code'}, format='json')
        # Past the permission gate: a bad code is a 404, not a 403.
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_kitchen_cannot_place_an_order(self):
        self.client.force_authenticate(self.kitchen)
        response = self.client.post(
            reverse('order-list'), {'pickup_time': '2030-01-01T12:00:00Z'},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
