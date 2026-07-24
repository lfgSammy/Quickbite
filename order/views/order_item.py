from django.db import transaction
from rest_framework import status
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from order.models import (Order, OrderItem, OrderItemDrink, OrderItemRiceExtra,
                          OrderItemShawarmaExtra, Cart)
from menu.models import MenuItem, MenuItemSize, RiceType, RiceExtra,ShawarmaExtra,Drink,ShawarmaOption
from order.serializers import OrderSerializer
from drf_spectacular.utils import extend_schema

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