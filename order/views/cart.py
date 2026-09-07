import uuid

from django.db import transaction
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from order.models import (Order,Cart, CartItem, CartItemDrink, CartItemRiceExtra,
                          CartItemShawarmaExtra)
from menu.models import (MenuItemSize, RiceType, RiceExtra, ShawarmaExtra,
                         Drink, ShawarmaOption)
from order.serializers import (CartItemCreateSerializer,
                               CartItemUpdateSerializer, CartSerializer,
                               ClaimCartSerializer,
                               RevertOrderResponseSerializer)
from drf_spectacular.utils import extend_schema

# Every relation the cart serializer and get_total() touch. Without these the
# cart was ~8 queries per line: get_total() walks extras and drinks, then the
# serializer re-reads all three plus the menu item.
CART_PREFETCH = (
    'items__menu_item',
    'items__size',
    'items__rice_type',
    'items__shawarma_option',
    'items__rice_extras__extra',
    'items__shawarma_extras__extra',
    'items__drinks__drink',
)

# Guests carry their cart in this header. It is the only thing identifying a
# guest cart, so the client stores it and sends it on every cart call.
CART_TOKEN_HEADER = 'X-Cart-Token'


def guest_cart_from_token(token):
    """Look up an unclaimed cart by token, or None."""
    if not token:
        return None
    try:
        token = uuid.UUID(str(token))
    except (ValueError, AttributeError, TypeError):
        # token is a UUIDField: a malformed value raises rather than simply
        # not matching, which would be a 500 on a stale client token.
        return None
    return Cart.objects.filter(token=token, customer__isnull=True).first()


def resolve_cart(request, create=True):
    """
    The cart this request is acting on.

    Signed in, it is the user's cart. Otherwise it is the guest cart named by
    the X-Cart-Token header - creating one if the caller has no usable token,
    so a first "add to cart" works with no account and no round trip.
    """
    if request.user.is_authenticated:
        cart, _ = Cart.objects.get_or_create(customer=request.user)
        return cart

    cart = guest_cart_from_token(request.headers.get(CART_TOKEN_HEADER))
    if cart or not create:
        return cart
    return Cart.objects.create()


def load_cart(cart):
    """Re-read a cart with everything the serializer needs already loaded."""
    return Cart.objects.prefetch_related(*CART_PREFETCH).get(pk=cart.pk)


def cart_response(cart, status_code=status.HTTP_200_OK):
    return Response(CartSerializer(load_cart(cart)).data, status=status_code)


class CartView(APIView):
    permission_classes = [AllowAny]
    serializer_class = CartSerializer

    def get(self, request):
        cart = resolve_cart(request, create=False)
        if cart is None:
            # No account and no token yet: an empty cart, without writing a row
            # for every anonymous visitor who merely loads the page.
            return Response({'id': None, 'items': [], 'total': '0.00',
                             'token': None, 'is_guest': True})
        return cart_response(cart)

    def delete(self, request):
        cart = resolve_cart(request, create=False)
        if cart:
            cart.items.all().delete()
        return Response({'message': 'Cart cleared'})


class CartItemView(APIView):
    permission_classes = [AllowAny]
    serializer_class = CartSerializer

    @extend_schema(request=CartItemCreateSerializer,
                   responses={201: CartSerializer})
    def post(self, request):
        cart = resolve_cart(request)

        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save(cart=cart)

        return cart_response(cart, status.HTTP_201_CREATED)


class CartItemDetailView(APIView):
    """
    Removing one line.

    Separate from CartItemView because both URLs used to point at that one
    class, so POST /cart/items/5/ and DELETE /cart/items/ each reached a method
    whose signature could not accept them - a TypeError, i.e. a 500.
    """

    permission_classes = [AllowAny]
    serializer_class = CartSerializer

    @extend_schema(responses={204: None})
    def delete(self, request, item_id):
        cart = resolve_cart(request, create=False)
        if cart is None:
            return Response({'error': 'Item not found in cart'},
                            status=status.HTTP_404_NOT_FOUND)
        cart_item = CartItem.objects.filter(id=item_id, cart=cart).first()
        if not cart_item:
            return Response({'error': 'Item not found in cart'},
                            status=status.HTTP_404_NOT_FOUND)
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateCartItemView(APIView):
    permission_classes = [AllowAny]
    serializer_class = CartSerializer

    @extend_schema(request=CartItemUpdateSerializer,
                   responses={200: CartSerializer})
    def patch(self, request, item_id):
        cart = resolve_cart(request, create=False)
        if cart is None:
            return Response({'error': 'Item not found in cart'},
                            status=status.HTTP_404_NOT_FOUND)

        cart_item = CartItem.objects.select_related('menu_item').filter(
            id=item_id, cart=cart).first()
        if not cart_item:
            return Response({'error': 'Item not found in cart'},
                            status=status.HTTP_404_NOT_FOUND)

        serializer = CartItemUpdateSerializer(
            cart_item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()

        return cart_response(cart)


class ClaimCartView(APIView):
    """
    Hand a guest cart to the account that just signed in.

    Called once after login or registration. If the user had no cart, the guest
    cart simply becomes theirs; if they already had one, the guest lines are
    moved across so nothing chosen while signed out is lost.
    """

    permission_classes = [IsAuthenticated]
    serializer_class = CartSerializer

    @extend_schema(request=ClaimCartSerializer,
                   responses={200: CartSerializer})
    def post(self, request):
        serializer = ClaimCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            guest = guest_cart_from_token(serializer.validated_data['token'])
            own = Cart.objects.filter(customer=request.user).first()

            if guest is None:
                # Nothing to claim - an already-claimed or expired token is not
                # an error, the caller just gets whatever cart they now have.
                own = own or Cart.objects.create(customer=request.user)
            elif own is None:
                guest.customer = request.user
                guest.save(update_fields=['customer'])
                own = guest
            else:
                guest.items.update(cart=own)
                guest.delete()

        return cart_response(own)


class RevertOrderToCartView(APIView):
    permission_classes = [IsAuthenticated]
    serializer_class = RevertOrderResponseSerializer

    def post(self, request, order_id):
        order = Order.objects.filter(
            id=order_id, customer=request.user).first()
        if not order:
            return Response({'error': 'Order not found'},
                            status=status.HTTP_404_NOT_FOUND)
        if order.status not in ['pending']:
            return Response(
                {'error': 'Only pending orders can be reverted'},
                status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # get or create cart
            cart, created = Cart.objects.get_or_create(
                customer=request.user)

            # clear existing cart
            cart.items.all().delete()

            # move order items back to cart
            for order_item in order.items.prefetch_related(
                'rice_extras', 'shawarma_extras', 'drinks'
            ).all():
                # find the original menu item
                menu_item = order_item.menu_item

                # find size by name
                size = None
                if order_item.size_name:
                    size = MenuItemSize.objects.filter(
                        menu_item=menu_item,
                        name=order_item.size_name
                    ).first()

                # find rice type by name
                rice_type = None
                if order_item.rice_type_name:
                    rice_type = RiceType.objects.filter(
                        name=order_item.rice_type_name
                    ).first()

                # find shawarma option by name
                shawarma_option = None
                if order_item.shawarma_option_name:
                    shawarma_option = ShawarmaOption.objects.filter(
                        menu_item=menu_item,
                        name=order_item.shawarma_option_name
                    ).first()

                # create cart item
                cart_item = CartItem.objects.create(
                    cart=cart,
                    menu_item=menu_item,
                    size=size,
                    rice_type=rice_type,
                    shawarma_option=shawarma_option,
                    quantity=order_item.quantity
                )

                # restore rice extras
                for extra in order_item.rice_extras.all():
                    rice_extra = RiceExtra.objects.filter(
                        name=extra.extra_name).first()
                    if rice_extra:
                        CartItemRiceExtra.objects.create(
                            cart_item=cart_item,
                            extra=rice_extra,
                            quantity=extra.quantity
                        )

                # restore shawarma extras
                for extra in order_item.shawarma_extras.all():
                    shawarma_extra = ShawarmaExtra.objects.filter(
                        name=extra.extra_name).first()
                    if shawarma_extra:
                        CartItemShawarmaExtra.objects.create(
                            cart_item=cart_item,
                            extra=shawarma_extra,
                            is_added=extra.is_added
                        )

                # restore drinks
                for drink in order_item.drinks.all():
                    drink_obj = Drink.objects.filter(
                        name=drink.drink_name).first()
                    if drink_obj:
                        CartItemDrink.objects.create(
                            cart_item=cart_item,
                            drink=drink_obj,
                            quantity=drink.quantity
                        )

            # cancel the order
            order.status = 'cancelled'
            order.save()

        serializer = CartSerializer(load_cart(cart))
        return Response({
            'message': 'Order reverted to cart successfully',
            'cart': serializer.data
        })
