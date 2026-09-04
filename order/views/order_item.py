from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from Quickbite.pagination import PaginatedListMixin
from Quickbite.permissions import IsCustomer, IsKitchenOrAdmin
from order.models import Cart, Order
from order.serializers import (OrderCreateSerializer, OrderSerializer,
                               OrderStatusSerializer)
from drf_spectacular.utils import extend_schema

@extend_schema(tags=['Orders'])
class OrderListView(PaginatedListMixin, APIView):
    def get_permissions(self):
        # Anyone signed in may list their own orders; only customers place them.
        if self.request.method == 'POST':
            return [IsCustomer()]
        return [IsAuthenticated()]

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

        return self.paginated_response(orders, OrderSerializer, request)

    @extend_schema(request=OrderCreateSerializer,
                   responses={201: OrderSerializer})
    def post(self, request):
        cart = Cart.objects.filter(customer=request.user).first()
        if not cart:
            return Response({'error': 'Your cart is empty'},
                            status=status.HTTP_400_BAD_REQUEST)

        serializer = OrderCreateSerializer(
            data=request.data, context={'cart': cart})
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            order = serializer.save()

        return Response(OrderSerializer(order).data,
                        status=status.HTTP_201_CREATED)


@extend_schema(tags=['Orders'])
class OrderDetailView(APIView):
    def get_permissions(self):
        # Reading is scoped to the owner in get_object(); only kitchen and
        # admins may move an order to another status.
        if self.request.method == 'PATCH':
            return [IsKitchenOrAdmin()]
        return [IsAuthenticated()]

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

    @extend_schema(request=OrderStatusSerializer,
                   responses={200: OrderSerializer})
    def patch(self, request, order_id):
        order = self.get_object(order_id, request.user)
        if not order:
            return Response({'error': 'Order not found'},
                            status=status.HTTP_404_NOT_FOUND)

        serializer = OrderStatusSerializer(order, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(OrderSerializer(order).data)

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