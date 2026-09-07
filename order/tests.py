from datetime import timedelta
from decimal import Decimal

from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from menu.models import (Drink, MenuItem, MenuItemSize, RiceExtra,
                        ShawarmaExtra, ShawarmaOption)
from order.models import (Cart, CartItem, CartItemDrink,
                         CartItemRiceExtra, Order)
from users.models import OperatingHours, User


class CartPricingTests(APITestCase):
    """Regressions for cart lines that used to price at zero."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='ada', email='ada@example.com',
            password='Passw0rdy', role='customer')
        self.client.force_authenticate(self.user)

        self.rice = MenuItem.objects.create(name='Party Jollof', item_type='rice')
        self.size = MenuItemSize.objects.create(
            menu_item=self.rice, name='Medium', price=Decimal('4000.00'))

    def test_deleting_a_size_removes_the_cart_line_instead_of_zeroing_it(self):
        cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(
            cart=cart, menu_item=self.rice, size=self.size, quantity=2)
        self.assertEqual(cart.get_total(), Decimal('8000.00'))

        self.size.delete()

        cart.refresh_from_db()
        # Previously the FK was SET_NULL, leaving a line with no price source
        # that get_base_price() reported as 0 - i.e. free food.
        self.assertEqual(cart.items.count(), 0)
        self.assertEqual(cart.get_total(), Decimal('0.00'))

    def test_untyped_menu_item_is_rejected_not_a_500(self):
        untyped = MenuItem.objects.create(name='Mystery Dish', item_type=None)
        response = self.client.post(
            reverse('cart-item-add'),
            {'menu_item_id': untyped.id, 'quantity': 1},
            format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_empty_cart_total_is_a_decimal(self):
        cart = Cart.objects.create(customer=self.user)
        self.assertIsInstance(cart.get_total(), Decimal)


class OrderCheckoutTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='bola', email='bola@example.com',
            password='Passw0rdy', role='customer')
        self.client.force_authenticate(self.user)

        self.shawarma = MenuItem.objects.create(
            name='Shawarma', item_type='shawarma')
        self.option = ShawarmaOption.objects.create(
            menu_item=self.shawarma, name='Beef', price=Decimal('4000.00'))

        # Open every day, all day, so hours never accidentally fail a test.
        for day in range(7):
            OperatingHours.objects.create(
                day=day, open_time='00:00', close_time='23:59', is_open=True)

        self.cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(
            cart=self.cart, menu_item=self.shawarma,
            shawarma_option=self.option, quantity=1)

    def _pickup(self, hours_ahead=2):
        return (timezone.now() + timedelta(hours=hours_ahead)).isoformat()

    def test_pickup_time_is_stored_as_a_datetime_not_a_string(self):
        response = self.client.post(
            reverse('order-list'),
            {'pickup_time': self._pickup()}, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        order = Order.objects.get(id=response.data['id'])
        self.assertIsInstance(order.pickup_time, timezone.datetime)

    def test_order_is_rejected_when_the_chosen_option_disappeared(self):
        self.option.delete()
        response = self.client.post(
            reverse('order-list'),
            {'pickup_time': self._pickup()}, format='json')
        # The cart line is gone with the option, so the cart is empty.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Order.objects.count(), 0)

    def test_pickup_time_in_the_past_is_rejected(self):
        response = self.client.post(
            reverse('order-list'),
            {'pickup_time': self._pickup(hours_ahead=-2)}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_pickup_is_checked_against_the_pickup_days_hours(self):
        pickup = timezone.localtime(timezone.now() + timedelta(days=1))
        OperatingHours.objects.filter(day=pickup.weekday()).update(is_open=False)

        response = self.client.post(
            reverse('order-list'),
            {'pickup_time': pickup.isoformat()}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Validation moved into OrderCreateSerializer, so errors now come back
        # keyed by field the way DRF reports them rather than under 'error'.
        self.assertIn('closed', str(response.data).lower())


class ResponseShapeTests(APITestCase):
    """The payload should carry what the caller needs and nothing else."""

    def setUp(self):
        self.user = User.objects.create_user(
            username='ngozi', email='ngozi@example.com',
            password='Passw0rdy', role='customer')
        self.client.force_authenticate(self.user)

        self.rice = MenuItem.objects.create(name='Party Jollof', item_type='rice')
        self.size = MenuItemSize.objects.create(
            menu_item=self.rice, name='Medium', price=Decimal('4000.00'))

        self.shawarma = MenuItem.objects.create(
            name='Shawarma', item_type='shawarma')
        self.beef = ShawarmaOption.objects.create(
            menu_item=self.shawarma, name='Beef', price=Decimal('4000.00'))
        self.sold_out = ShawarmaOption.objects.create(
            menu_item=self.shawarma, name='Mixed',
            price=Decimal('4400.00'), is_available=False)

    def test_menu_returns_only_the_options_that_apply_to_each_item(self):
        response = self.client.get(reverse('menu-list'))
        by_name = {item['name']: item for item in response.data}

        rice = by_name['Party Jollof']
        self.assertIn('sizes', rice)
        self.assertNotIn('shawarma_options', rice)

        shawarma = by_name['Shawarma']
        self.assertIn('shawarma_options', shawarma)
        self.assertNotIn('sizes', shawarma)

    def test_sold_out_shawarma_options_are_not_offered(self):
        response = self.client.get(reverse('menu-list'))
        shawarma = next(i for i in response.data if i['name'] == 'Shawarma')
        names = [o['name'] for o in shawarma['shawarma_options']]
        self.assertEqual(names, ['Beef'])

    def test_cart_line_carries_a_slim_menu_item_not_the_whole_menu_entry(self):
        cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(
            cart=cart, menu_item=self.rice, size=self.size, quantity=1)

        response = self.client.get(reverse('cart'))
        menu_item = response.data['items'][0]['menu_item']

        self.assertEqual(
            set(menu_item), {'id', 'name', 'image_url', 'item_type'})
        # the parts that made the cart response heavy
        self.assertNotIn('sizes', menu_item)
        self.assertNotIn('created_at', menu_item)

    def test_money_is_a_string_everywhere_in_one_payload(self):
        cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(
            cart=cart, menu_item=self.rice, size=self.size, quantity=2)

        response = self.client.get(reverse('cart'))
        line = response.data['items'][0]

        self.assertEqual(response.data['total'], '8000.00')
        self.assertEqual(line['total'], '8000.00')
        self.assertEqual(line['size']['price'], '4000.00')
        for value in (response.data['total'], line['total'],
                      line['size']['price']):
            self.assertIsInstance(value, str)

    def test_drinks_key_is_present_even_when_empty(self):
        cart = Cart.objects.create(customer=self.user)
        CartItem.objects.create(
            cart=cart, menu_item=self.rice, size=self.size, quantity=1)

        response = self.client.get(reverse('cart'))
        # Used to vanish whenever the list happened to be empty, so the
        # response shape depended on data rather than on the item's type.
        self.assertEqual(response.data['items'][0]['drinks'], [])

    def test_cart_read_does_not_scale_queries_with_line_count(self):
        cart = Cart.objects.create(customer=self.user)

        def queries_for(line_count):
            cart.items.all().delete()
            for _ in range(line_count):
                CartItem.objects.create(
                    cart=cart, menu_item=self.rice,
                    size=self.size, quantity=1)
            with CaptureQueriesContext(connection) as ctx:
                self.client.get(reverse('cart'))
            return len(ctx.captured_queries)

        # Without prefetching this was ~8 queries *per line*: get_total()
        # walks extras and drinks, then the serializer re-reads all three.
        self.assertEqual(queries_for(3), queries_for(12))
        self.assertLessEqual(queries_for(12), 10)


class DrinkPricingTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='tunde', email='tunde@example.com',
            password='Passw0rdy', role='customer')
        self.rice = MenuItem.objects.create(name='Party Jollof', item_type='rice')
        self.size = MenuItemSize.objects.create(
            menu_item=self.rice, name='Medium', price=Decimal('4000.00'))
        self.coke = Drink.objects.create(name='Coke', price=Decimal('500.00'))
        self.plantain = RiceExtra.objects.create(
            name='Plantain', price=Decimal('300.00'), max_quantity=5)

    def test_a_drink_is_not_multiplied_by_the_food_quantity(self):
        cart = Cart.objects.create(customer=self.user)
        line = CartItem.objects.create(
            cart=cart, menu_item=self.rice, size=self.size, quantity=3)
        CartItemDrink.objects.create(cart_item=line, drink=self.coke, quantity=1)

        # 3 plates at 4000, plus exactly one 500 Coke - not three.
        self.assertEqual(line.get_drinks_total(), Decimal('500.00'))
        self.assertEqual(line.get_total(), Decimal('12500.00'))

    def test_a_drinks_own_quantity_still_counts(self):
        cart = Cart.objects.create(customer=self.user)
        line = CartItem.objects.create(
            cart=cart, menu_item=self.rice, size=self.size, quantity=2)
        CartItemDrink.objects.create(cart_item=line, drink=self.coke, quantity=4)

        self.assertEqual(line.get_drinks_total(), Decimal('2000.00'))

    def test_extras_do_still_scale_with_the_food_quantity(self):
        cart = Cart.objects.create(customer=self.user)
        line = CartItem.objects.create(
            cart=cart, menu_item=self.rice, size=self.size, quantity=3)
        CartItemRiceExtra.objects.create(
            cart_item=line, extra=self.plantain, quantity=1)

        # An extra is per-plate: 3 plates each with plantain = 3 plantains.
        self.assertEqual(line.get_extras_total(), Decimal('900.00'))


class CartValidationTests(APITestCase):
    """
    Bad input used to be dropped in silence and still return 201. These pin
    the rules now that they live in the serializer.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='amaka', email='amaka@example.com',
            password='Passw0rdy', role='customer')
        self.client.force_authenticate(self.user)

        self.rice = MenuItem.objects.create(name='Party Jollof', item_type='rice')
        self.size = MenuItemSize.objects.create(
            menu_item=self.rice, name='Medium', price=Decimal('4000.00'))

        self.other_rice = MenuItem.objects.create(
            name='Fried Rice', item_type='rice')
        self.other_size = MenuItemSize.objects.create(
            menu_item=self.other_rice, name='Big', price=Decimal('5000.00'))

        self.shawarma = MenuItem.objects.create(
            name='Shawarma', item_type='shawarma')
        self.beef = ShawarmaOption.objects.create(
            menu_item=self.shawarma, name='Beef', price=Decimal('4000.00'))

        self.plantain = RiceExtra.objects.create(
            name='Plantain', price=Decimal('300.00'), max_quantity=3)
        self.sold_out_extra = RiceExtra.objects.create(
            name='Coleslaw', price=Decimal('200.00'), is_available=False)
        self.coke = Drink.objects.create(name='Coke', price=Decimal('500.00'))
        self.sold_out_drink = Drink.objects.create(
            name='Fanta', price=Decimal('500.00'), is_available=False)

    def add(self, payload):
        return self.client.post(reverse('cart-item-add'), payload, format='json')

    def test_a_valid_line_is_accepted(self):
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.size.id,
            'quantity': 2,
            'rice_extras': [{'extra_id': self.plantain.id, 'quantity': 2}],
            'drinks': [{'drink_id': self.coke.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(CartItem.objects.count(), 1)

    def test_unknown_extra_is_rejected_not_silently_dropped(self):
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.size.id,
            'rice_extras': [{'extra_id': 99999, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_sold_out_extra_is_rejected(self):
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.size.id,
            'rice_extras': [{'extra_id': self.sold_out_extra.id,
                             'quantity': 1}],
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_sold_out_drink_is_rejected(self):
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.size.id,
            'drinks': [{'drink_id': self.sold_out_drink.id, 'quantity': 1}],
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_exceeding_max_quantity_errors_instead_of_clamping(self):
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.size.id,
            'rice_extras': [{'extra_id': self.plantain.id, 'quantity': 99}],
        })
        # Used to silently become 3 and return 201.
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_a_size_from_another_menu_item_is_rejected(self):
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.other_size.id,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_rice_requires_a_size(self):
        response = self.add({'menu_item_id': self.rice.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_shawarma_requires_an_option(self):
        response = self.add({'menu_item_id': self.shawarma.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_shawarma_extras_cannot_go_on_a_rice_item(self):
        extra = ShawarmaExtra.objects.create(
            name='Garlic Sauce', price=Decimal('200.00'))
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.size.id,
            'shawarma_extras': [{'extra_id': extra.id, 'is_added': True}],
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unavailable_menu_item_is_rejected(self):
        self.rice.is_available = False
        self.rice.save()
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.size.id})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_zero_quantity_is_rejected(self):
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.size.id,
            'quantity': 0})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_nothing_is_written_when_one_child_row_is_invalid(self):
        response = self.add({
            'menu_item_id': self.rice.id, 'size_id': self.size.id,
            'rice_extras': [
                {'extra_id': self.plantain.id, 'quantity': 1},
                {'extra_id': self.sold_out_extra.id, 'quantity': 1},
            ],
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # The good row must not survive on its own.
        self.assertEqual(CartItem.objects.count(), 0)
        self.assertEqual(CartItemRiceExtra.objects.count(), 0)


class CartUpdateValidationTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='ola', email='ola@example.com',
            password='Passw0rdy', role='customer')
        self.client.force_authenticate(self.user)

        self.rice = MenuItem.objects.create(name='Party Jollof', item_type='rice')
        self.size = MenuItemSize.objects.create(
            menu_item=self.rice, name='Medium', price=Decimal('4000.00'))
        self.plantain = RiceExtra.objects.create(
            name='Plantain', price=Decimal('300.00'), max_quantity=3)

        cart = Cart.objects.create(customer=self.user)
        self.line = CartItem.objects.create(
            cart=cart, menu_item=self.rice, size=self.size, quantity=1)

    def patch(self, payload):
        return self.client.patch(
            reverse('update-cart-item', args=[self.line.id]),
            payload, format='json')

    def test_quantity_can_be_updated(self):
        response = self.patch({'quantity': 4})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, 4)

    def test_quantity_below_one_is_rejected(self):
        response = self.patch({'quantity': 0})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, 1)

    def test_extras_are_replaced_wholesale(self):
        self.patch({'rice_extras': [
            {'extra_id': self.plantain.id, 'quantity': 2}]})
        self.assertEqual(self.line.rice_extras.count(), 1)

        self.patch({'rice_extras': []})
        self.assertEqual(self.line.rice_extras.count(), 0)

    def test_update_enforces_max_quantity_too(self):
        response = self.patch({'rice_extras': [
            {'extra_id': self.plantain.id, 'quantity': 99}]})
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(self.line.rice_extras.count(), 0)

    def test_another_users_line_cannot_be_updated(self):
        stranger = User.objects.create_user(
            username='intruder', email='intruder@example.com',
            password='Passw0rdy', role='customer')
        self.client.force_authenticate(stranger)

        response = self.patch({'quantity': 99})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.line.refresh_from_db()
        self.assertEqual(self.line.quantity, 1)


class CartItemRoutingTests(APITestCase):
    """
    Both cart-item URLs used to resolve to the same view, so each exposed a
    method it could not actually accept.
    """

    def setUp(self):
        self.user = User.objects.create_user(
            username='routing', email='routing@example.com',
            password='Passw0rdy', role='customer')
        self.client.force_authenticate(self.user)
        rice = MenuItem.objects.create(name='Jollof', item_type='rice')
        size = MenuItemSize.objects.create(
            menu_item=rice, name='Medium', price=Decimal('4000.00'))
        cart = Cart.objects.create(customer=self.user)
        self.line = CartItem.objects.create(
            cart=cart, menu_item=rice, size=size, quantity=1)

    def test_deleting_a_line_works(self):
        response = self.client.delete(
            reverse('cart-item-delete', args=[self.line.id]))
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)
        self.assertEqual(CartItem.objects.count(), 0)

    def test_posting_to_a_specific_line_is_not_allowed(self):
        response = self.client.post(
            reverse('cart-item-delete', args=[self.line.id]), {}, format='json')
        # 405, not the TypeError-driven 500 it used to be.
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_deleting_the_whole_collection_is_not_allowed(self):
        response = self.client.delete(reverse('cart-item-add'))
        self.assertEqual(
            response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)
        self.assertEqual(CartItem.objects.count(), 1)


class GuestCartTests(APITestCase):
    """
    A cart no longer needs an account. Requiring sign-up before the first
    "add to cart" lost people at the moment they had decided to buy.
    """

    def setUp(self):
        self.rice = MenuItem.objects.create(name='Party Jollof', item_type='rice')
        self.size = MenuItemSize.objects.create(
            menu_item=self.rice, name='Medium', price=Decimal('4000.00'))

    def add_as_guest(self, token=None, quantity=1):
        headers = {'HTTP_X_CART_TOKEN': token} if token else {}
        return self.client.post(
            reverse('cart-item-add'),
            {'menu_item_id': self.rice.id, 'size_id': self.size.id,
             'quantity': quantity},
            format='json', **headers)

    def test_a_guest_can_add_to_cart_without_an_account(self):
        response = self.add_as_guest()

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(response.data['is_guest'])
        self.assertIsNotNone(response.data['token'])
        self.assertEqual(response.data['total'], '4000.00')

    def test_the_token_brings_the_same_cart_back(self):
        token = self.add_as_guest().data['token']

        self.add_as_guest(token=token)
        response = self.client.get(
            reverse('cart'), HTTP_X_CART_TOKEN=token)

        self.assertEqual(len(response.data['items']), 2)
        self.assertEqual(Cart.objects.count(), 1)

    def test_without_a_token_a_guest_gets_a_different_cart(self):
        first = self.add_as_guest().data['token']
        second = self.add_as_guest().data['token']
        self.assertNotEqual(first, second)

    def test_reading_a_cart_with_no_token_creates_nothing(self):
        response = self.client.get(reverse('cart'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['items'], [])
        # A row per anonymous visitor who merely loads the page would be waste.
        self.assertEqual(Cart.objects.count(), 0)

    def test_a_malformed_token_is_not_a_500(self):
        response = self.client.get(
            reverse('cart'), HTTP_X_CART_TOKEN='not-a-uuid')
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_a_guest_cannot_place_an_order(self):
        token = self.add_as_guest().data['token']
        response = self.client.post(
            reverse('order-list'), {'pickup_time': '2030-01-01T12:00:00Z'},
            format='json', HTTP_X_CART_TOKEN=token)
        # Checkout is where the account is genuinely needed.
        self.assertIn(response.status_code,
                      (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN))

    def test_a_guest_cannot_reach_another_guests_cart_line(self):
        mine = self.add_as_guest()
        theirs_token = self.add_as_guest().data['token']
        line_id = mine.data['items'][0]['id']

        response = self.client.delete(
            reverse('cart-item-delete', args=[line_id]),
            HTTP_X_CART_TOKEN=theirs_token)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(CartItem.objects.filter(id=line_id).count(), 1)


class ClaimCartTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username='claimer', email='claimer@example.com',
            password='Passw0rdy', role='customer')
        self.rice = MenuItem.objects.create(name='Party Jollof', item_type='rice')
        self.size = MenuItemSize.objects.create(
            menu_item=self.rice, name='Medium', price=Decimal('4000.00'))

    def guest_cart_with_one_line(self):
        response = self.client.post(
            reverse('cart-item-add'),
            {'menu_item_id': self.rice.id, 'size_id': self.size.id,
             'quantity': 1},
            format='json')
        return response.data['token']

    def claim(self, token):
        self.client.force_authenticate(self.user)
        return self.client.post(
            reverse('cart-claim'), {'token': token}, format='json')

    def test_claiming_gives_the_guest_cart_to_the_user(self):
        token = self.guest_cart_with_one_line()

        response = self.claim(token)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['is_guest'])
        self.assertEqual(len(response.data['items']), 1)
        self.assertEqual(Cart.objects.filter(customer=self.user).count(), 1)
        self.assertEqual(Cart.objects.filter(customer__isnull=True).count(), 0)

    def test_claiming_merges_into_a_cart_the_user_already_had(self):
        existing = Cart.objects.create(customer=self.user)
        CartItem.objects.create(
            cart=existing, menu_item=self.rice, size=self.size, quantity=2)

        token = self.guest_cart_with_one_line()
        response = self.claim(token)

        # Nothing chosen while signed out is lost.
        self.assertEqual(len(response.data['items']), 2)
        self.assertEqual(response.data['total'], '12000.00')
        self.assertEqual(Cart.objects.filter(customer__isnull=True).count(), 0)

    def test_claiming_an_unknown_token_is_not_an_error(self):
        import uuid as _uuid
        response = self.claim(str(_uuid.uuid4()))

        # An already-claimed or expired token just means there was nothing to
        # merge; the caller still gets their own cart back.
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['items'], [])

    def test_a_claimed_cart_stops_answering_to_its_old_token(self):
        token = self.guest_cart_with_one_line()
        self.claim(token)

        self.client.force_authenticate(user=None)
        response = self.client.get(reverse('cart'), HTTP_X_CART_TOKEN=token)

        self.assertEqual(response.data['items'], [])
        self.assertIsNone(response.data['id'])

    def test_a_signed_in_user_ignores_a_stray_token(self):
        token = self.guest_cart_with_one_line()
        self.client.force_authenticate(self.user)

        response = self.client.get(reverse('cart'), HTTP_X_CART_TOKEN=token)

        # Signed in, the account decides which cart is yours - not a header.
        self.assertFalse(response.data['is_guest'])
        self.assertEqual(response.data['items'], [])
