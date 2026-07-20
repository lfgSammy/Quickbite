from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import (Cart, CartItem, CartItemRiceExtra,
                     CartItemShawarmaExtra, CartItemDrink,
                     Order, OrderItem, OrderItemRiceExtra,
                     OrderItemShawarmaExtra, OrderItemDrink)
from .serializers import CartSerializer, CartItemSerializer, OrderSerializer
from menu.models import MenuItem, MenuItemSize, RiceType, ShawarmaOption, RiceExtra, ShawarmaExtra, Drink
from drf_spectacular.utils import extend_schema

class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, created = Cart.objects.get_or_create(customer=request.user)
        serializer = CartSerializer(cart)
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

        serializer = CartSerializer(cart)
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


class CancelOrderView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        order = Order.objects.filter(
            id=order_id, customer=request.user).first()
        if not order:
            return Response({'error': 'Order not found'},
                            status=status.HTTP_404_NOT_FOUND)
        if order.status not in ['pending']:
            return Response(
                {'error': 'Only pending orders can be cancelled'},
                status=status.HTTP_400_BAD_REQUEST)
        order.status = 'cancelled'
        order.save()
        return Response({'message': 'Order cancelled successfully'})


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

        serializer = CartSerializer(cart)
        return Response({
            'message': 'Order reverted to cart successfully',
            'cart': serializer.data
        })


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

        serializer = CartSerializer(cart)
        return Response(serializer.data)

@extend_schema(tags=['Cart'])
class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if request.user.is_admin or request.user.is_kitchen:
            orders = Order.objects.select_related('customer').prefetch_related(
                'items__rice_extras',
                'items__shawarma_extras',
                'items__drinks'
            ).all().order_by('-created_at')
        else:
            orders = Order.objects.select_related('customer').prefetch_related(
                'items__rice_extras',
                'items__shawarma_extras',
                'items__drinks'
            ).filter(customer=request.user).order_by('-created_at')

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    @extend_schema(request=OrderSerializer)
    def post(self, request):
        if not request.user.is_customer:
            return Response({'error': 'Only customers can place orders'},
                            status=status.HTTP_403_FORBIDDEN)

        cart = Cart.objects.filter(customer=request.user).first()
        if not cart or not cart.items.exists():
            return Response({'error': 'Your cart is empty'},
                            status=status.HTTP_400_BAD_REQUEST)

        pickup_time = request.data.get('pickup_time')
        if not pickup_time:
            return Response({'error': 'Pickup time is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        total_amount = cart.get_total()

        with transaction.atomic():
            order = Order.objects.create(
                customer=request.user,
                pickup_time=pickup_time,
                total_amount=total_amount,
                status='pending'
            )

            for cart_item in cart.items.prefetch_related(
                'rice_extras__extra',
                'shawarma_extras__extra',
                'drinks__drink'
            ).all():
                # determine size and shawarma info
                size_name = cart_item.size.name if cart_item.size else ''
                size_price = cart_item.size.price if cart_item.size else 0
                rice_type_name = cart_item.rice_type.name if cart_item.rice_type else ''
                shawarma_option_name = (cart_item.shawarma_option.name
                                        if cart_item.shawarma_option else '')
                shawarma_option_price = (cart_item.shawarma_option.price
                                         if cart_item.shawarma_option else 0)

                order_item = OrderItem.objects.create(
                    order=order,
                    menu_item=cart_item.menu_item,
                    size_name=size_name,
                    size_price=size_price,
                    rice_type_name=rice_type_name,
                    shawarma_option_name=shawarma_option_name,
                    shawarma_option_price=shawarma_option_price,
                    quantity=cart_item.quantity,
                    item_total=cart_item.get_total()
                )

                # freeze rice extras
                for rice_extra in cart_item.rice_extras.all():
                    OrderItemRiceExtra.objects.create(
                        order_item=order_item,
                        extra_name=rice_extra.extra.name,
                        extra_price=rice_extra.extra.price,
                        quantity=rice_extra.quantity
                    )

                # freeze shawarma extras
                for shawarma_extra in cart_item.shawarma_extras.all():
                    OrderItemShawarmaExtra.objects.create(
                        order_item=order_item,
                        extra_name=shawarma_extra.extra.name,
                        extra_price=shawarma_extra.extra.price,
                        is_added=shawarma_extra.is_added
                    )

                # freeze drinks
                for drink in cart_item.drinks.all():
                    OrderItemDrink.objects.create(
                        order_item=order_item,
                        drink_name=drink.drink.name,
                        drink_price=drink.drink.price,
                        quantity=drink.quantity
                    )

            # clear cart
            cart.items.all().delete()

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


@extend_schema(tags=['Cart'])
class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, order_id, user):
        try:
            order = Order.objects.select_related('customer').prefetch_related(
                'items__rice_extras',
                'items__shawarma_extras',
                'items__drinks'
            ).get(id=order_id)
            if user.is_customer and order.customer != user:
                return None
            return order
        except Order.DoesNotExist:
            return None

    def get(self, request, order_id):
        order = self.get_object(order_id, request.user)
        if not order:
            return Response({'error': 'Order not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = OrderSerializer(order)
        return Response(serializer.data)

    def patch(self, request, order_id):
        if not request.user.is_kitchen and not request.user.is_admin:
            return Response(
                {'error': 'Only kitchen staff and admins can update order status'},
                status=status.HTTP_403_FORBIDDEN)

        order = self.get_object(order_id, request.user)
        if not order:
            return Response({'error': 'Order not found'},
                            status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        valid_statuses = ['preparing', 'ready', 'cancelled']

        if new_status not in valid_statuses:
            return Response(
                {'error': f'Invalid status. Choose from {valid_statuses}'},
                status=status.HTTP_400_BAD_REQUEST)

        # can only update paid orders
        if order.status not in ['paid', 'preparing']:
            return Response(
                {'error': f'Cannot update order with status: {order.status}'},
                status=status.HTTP_400_BAD_REQUEST)

        order.status = new_status
        order.save()
        serializer = OrderSerializer(order)
        return Response(serializer.data)


@extend_schema(tags=['Cart'])
class VerifyQRView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        if not request.user.is_kitchen and not request.user.is_admin:
            return Response({'error': 'Not authorized'},
                            status=status.HTTP_403_FORBIDDEN)

        qr_code = request.data.get('qr_code')
        if not qr_code:
            return Response({'error': 'QR code is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        order = Order.objects.filter(qr_code=qr_code).first()
        if not order:
            return Response({'error': 'Invalid QR code'},
                            status=status.HTTP_404_NOT_FOUND)

        if order.status == 'collected':
            return Response({'error': 'Order already collected'},
                            status=status.HTTP_400_BAD_REQUEST)

        if order.status != 'ready':
            return Response(
                {'error': f'Order not ready. Current status: {order.status}'},
                status=status.HTTP_400_BAD_REQUEST)

        order.status = 'collected'
        order.save()

        serializer = OrderSerializer(order)
        return Response({
            'message': 'Order collected successfully',
            'order': serializer.data
        })


@extend_schema(tags=['Cart'])
class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_admin:
            return Response({'error': 'Admin access required'},
                            status=status.HTTP_403_FORBIDDEN)

        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta

        today = timezone.now().date()
        week_ago = today - timedelta(days=7)

        total_orders = Order.objects.count()
        today_orders = Order.objects.filter(created_at__date=today).count()

        total_revenue = Order.objects.filter(
            status__in=['paid', 'preparing', 'ready', 'collected']
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        today_revenue = Order.objects.filter(
            created_at__date=today,
            status__in=['paid', 'preparing', 'ready', 'collected']
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        weekly_revenue = Order.objects.filter(
            created_at__date__gte=week_ago,
            status__in=['paid', 'preparing', 'ready', 'collected']
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        status_breakdown = Order.objects.values('status').annotate(
            count=Count('id'))

        pending_orders = Order.objects.filter(
            status__in=['paid', 'preparing']
        ).select_related('customer').prefetch_related(
            'items__rice_extras',
            'items__shawarma_extras',
            'items__drinks'
        ).order_by('pickup_time')

        pending_serializer = OrderSerializer(pending_orders, many=True)

        return Response({
            'overview': {
                'total_orders': total_orders,
                'today_orders': today_orders,
                'total_revenue': total_revenue,
                'today_revenue': today_revenue,
                'weekly_revenue': weekly_revenue,
            },
            'status_breakdown': list(status_breakdown),
            'pending_orders': pending_serializer.data
        })