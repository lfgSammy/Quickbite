from django.db import transaction
from rest_framework import status
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from order.models import (Order,Cart, CartItem, CartItemDrink, CartItemRiceExtra,
                          CartItemShawarmaExtra)
from menu.models import MenuItem, MenuItemSize, RiceType, RiceExtra,ShawarmaExtra,Drink,ShawarmaOption
from order.serializers import CartItemSerializer, CartSerializer
from drf_spectacular.utils import extend_schema, inline_serializer

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

    @extend_schema(request=CartItemSerializer)
    def post(self, request):
        cart, created = Cart.objects.get_or_create(customer=request.user)

        menu_item_id = request.data.get('menu_item_id')
        quantity = int(request.data.get('quantity', 1))
        size_id = request.data.get('size_id')
        rice_type_id = request.data.get('rice_type_id')
        shawarma_option_id = request.data.get('shawarma_option_id')
        rice_extras = request.data.get('rice_extras', [])
        shawarma_extras = request.data.get('shawarma_extras', [])
        drinks = request.data.get('drinks', [])

        # validate menu item
        menu_item = MenuItem.objects.filter(
            id=menu_item_id, is_available=True).first()
        if not menu_item:
            return Response({'error': 'Menu item unavailable'},
                            status=status.HTTP_404_NOT_FOUND)

        # validate based on item type
        if menu_item.item_type == 'rice':
            if not size_id:
                return Response({'error': 'Size is required for rice items'},
                                status=status.HTTP_400_BAD_REQUEST)
            size = MenuItemSize.objects.filter(
                id=size_id, menu_item=menu_item).first()
            if not size:
                return Response({'error': 'Invalid size for this menu item'},
                                status=status.HTTP_400_BAD_REQUEST)
            rice_type = None
            if rice_type_id:
                rice_type = RiceType.objects.filter(id=rice_type_id).first()
            shawarma_option = None

        elif menu_item.item_type == 'shawarma':
            if not shawarma_option_id:
                return Response(
                    {'error': 'Shawarma option is required'},
                    status=status.HTTP_400_BAD_REQUEST)
            shawarma_option = ShawarmaOption.objects.filter(
                id=shawarma_option_id,
                menu_item=menu_item,
                is_available=True
            ).first()
            if not shawarma_option:
                return Response({'error': 'Invalid shawarma option'},
                                status=status.HTTP_400_BAD_REQUEST)
            size = None
            rice_type = None

        else:
            # item_type is nullable on MenuItem, so an item with no type set
            # used to fall through both branches and raise UnboundLocalError
            # on the create() below - a 500 where a 400 belongs.
            return Response(
                {'error': 'This menu item is not configured for ordering yet'},
                status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # create cart item
            cart_item = CartItem.objects.create(
                cart=cart,
                menu_item=menu_item,
                size=size if menu_item.item_type == 'rice' else None,
                rice_type=rice_type,
                shawarma_option=shawarma_option,
                quantity=quantity
            )

            # add rice extras
            if menu_item.item_type == 'rice' and rice_extras:
                for extra_data in rice_extras:
                    extra = RiceExtra.objects.filter(
                        id=extra_data.get('extra_id'),
                        is_available=True
                    ).first()
                    if extra:
                        qty = int(extra_data.get('quantity', 1))
                        # enforce max quantity
                        if qty > extra.max_quantity:
                            qty = extra.max_quantity
                        CartItemRiceExtra.objects.create(
                            cart_item=cart_item,
                            extra=extra,
                            quantity=qty
                        )

            # add shawarma extras (toggles)
            if menu_item.item_type == 'shawarma' and shawarma_extras:
                for extra_data in shawarma_extras:
                    extra = ShawarmaExtra.objects.filter(
                        id=extra_data.get('extra_id'),
                        is_available=True
                    ).first()
                    if extra:
                        CartItemShawarmaExtra.objects.create(
                            cart_item=cart_item,
                            extra=extra,
                            is_added=extra_data.get('is_added', True)
                        )

            # add drinks
            if drinks:
                for drink_data in drinks:
                    drink = Drink.objects.filter(
                        id=drink_data.get('drink_id'),
                        is_available=True
                    ).first()
                    if drink:
                        CartItemDrink.objects.create(
                            cart_item=cart_item,
                            drink=drink,
                            quantity=int(drink_data.get('quantity', 1))
                        )

        serializer = CartSerializer(load_cart(request.user))
        return Response(serializer.data, status=status.HTTP_201_CREATED)


    @extend_schema(responses={204:None})
    def delete(self, request, item_id):
        cart = Cart.objects.filter(customer=request.user).first()
        if not cart:
            return Response({'error': 'Cart not found'},
                            status=status.HTTP_404_NOT_FOUND)
        cart_item = CartItem.objects.filter(id=item_id, cart=cart).first()
        if not cart_item:
            return Response({'error': 'Item not found in cart'},
                            status=status.HTTP_404_NOT_FOUND)
        cart_item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

class UpdateCartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        cart = Cart.objects.filter(customer=request.user).first()
        if not cart:
            return Response({'error': 'Cart not found'},
                            status=status.HTTP_404_NOT_FOUND)

        cart_item = CartItem.objects.filter(
            id=item_id, cart=cart).first()
        if not cart_item:
            return Response({'error': 'Item not found in cart'},
                            status=status.HTTP_404_NOT_FOUND)

        quantity = request.data.get('quantity')
        if quantity is not None:
            quantity = int(quantity)
            if quantity < 1:
                return Response({'error': 'Quantity must be at least 1'},
                                status=status.HTTP_400_BAD_REQUEST)
            cart_item.quantity = quantity
            cart_item.save()

        # update drinks
        drinks = request.data.get('drinks')
        if drinks is not None:
            cart_item.drinks.all().delete()
            for drink_data in drinks:
                drink = Drink.objects.filter(
                    id=drink_data.get('drink_id'),
                    is_available=True
                ).first()
                if drink:
                    CartItemDrink.objects.create(
                        cart_item=cart_item,
                        drink=drink,
                        quantity=int(drink_data.get('quantity', 1))
                    )

        # update rice extras
        rice_extras = request.data.get('rice_extras')
        if rice_extras is not None:
            cart_item.rice_extras.all().delete()
            for extra_data in rice_extras:
                extra = RiceExtra.objects.filter(
                    id=extra_data.get('extra_id'),
                    is_available=True
                ).first()
                if extra:
                    qty = int(extra_data.get('quantity', 1))
                    if qty > extra.max_quantity:
                        qty = extra.max_quantity
                    CartItemRiceExtra.objects.create(
                        cart_item=cart_item,
                        extra=extra,
                        quantity=qty
                    )

        # update shawarma extras
        shawarma_extras = request.data.get('shawarma_extras')
        if shawarma_extras is not None:
            cart_item.shawarma_extras.all().delete()
            for extra_data in shawarma_extras:
                extra = ShawarmaExtra.objects.filter(
                    id=extra_data.get('extra_id'),
                    is_available=True
                ).first()
                if extra:
                    CartItemShawarmaExtra.objects.create(
                        cart_item=cart_item,
                        extra=extra,
                        is_added=extra_data.get('is_added', True)
                    )

        serializer = CartSerializer(load_cart(request.user))
        return Response(serializer.data)
    
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
