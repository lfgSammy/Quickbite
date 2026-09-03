from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from order.models import (Order,Cart, CartItem, CartItemDrink, CartItemRiceExtra,
                          CartItemShawarmaExtra)
from menu.models import (MenuItemSize, RiceType, RiceExtra, ShawarmaExtra,
                         Drink, ShawarmaOption)
from order.serializers import (CartItemCreateSerializer,
                               CartItemUpdateSerializer, CartSerializer)
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


def load_cart(user):
    """The user's cart with everything the serializer needs already loaded."""
    cart, _ = Cart.objects.get_or_create(customer=user)
    return Cart.objects.prefetch_related(*CART_PREFETCH).get(pk=cart.pk)


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        serializer = CartSerializer(load_cart(request.user))
        return Response(serializer.data)

    def delete(self, request):
        cart = Cart.objects.filter(customer=request.user).first()
        if cart:
            cart.items.all().delete()
        return Response({'message': 'Cart cleared'})


class CartItemView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=CartItemCreateSerializer,
                   responses={201: CartSerializer})
    def post(self, request):
        cart, _ = Cart.objects.get_or_create(customer=request.user)

        serializer = CartItemCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save(cart=cart)

        return Response(CartSerializer(load_cart(request.user)).data,
                        status=status.HTTP_201_CREATED)

    @extend_schema(responses={204: None})
    def delete(self, request, item_id):
        cart_item = CartItem.objects.filter(
            id=item_id, cart__customer=request.user).first()
        if not cart_item:
            return Response({'error': 'Item not found in cart'},
                            status=status.HTTP_404_NOT_FOUND)
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    @extend_schema(request=CartItemUpdateSerializer,
                   responses={200: CartSerializer})
    def patch(self, request, item_id):
        cart_item = CartItem.objects.select_related('menu_item').filter(
            id=item_id, cart__customer=request.user).first()
        if not cart_item:
            return Response({'error': 'Item not found in cart'},
                            status=status.HTTP_404_NOT_FOUND)

        serializer = CartItemUpdateSerializer(
            cart_item, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        with transaction.atomic():
            serializer.save()

        return Response(CartSerializer(load_cart(request.user)).data)


class RevertOrderToCartView(APIView):
    permission_classes = [IsAuthenticated]

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

        serializer = CartSerializer(load_cart(request.user))
        return Response({
            'message': 'Order reverted to cart successfully',
            'cart': serializer.data
        })
