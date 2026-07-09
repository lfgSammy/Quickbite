from django.db import transaction
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import Cart, CartItem, Order, OrderItem
from .serializers import CartSerializer, CartItemSerializer, OrderSerializer
from menu.models import MenuItem
from django.db.models import Sum, Count
from django.utils import timezone
from datetime import timedelta

class AdminDashboardView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not request.user.is_admin_user:
            return Response({'error':'Admin access required'},
                            status=status.HTTP_403_FORBIDDEN)
        
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today -timedelta(days=30)

        #total orders
        total_orders = Order.objects.count()
        #don't forget
        today_orders = Order.objects.filter(created_at__date=today).count()

        #revenue
        total_revenue = Order.objects.filter(
            status__in = ['paid','preparing','ready','collected']
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        today_revenue = Order.objects.filter(
            created_at__today = today,
            status__in = ['paid','preparing','ready','collected']
        ).aggregate(total=Sum('total_amount'))['total'] or 0

        weekly_revenue = Order.objects.filter(
            created_at__date__gte = week_ago,
            status__in = ['paid', 'preparing', 'ready','collected']
        ).aggregate(total = Sum('total_amount'))['total'] or 0

        #order status breakdown
        status_breakdown = Order.objects.values('status').annotate(
            count=Count('id')
        )

        #popular items
        popular_items = OrderItem.objects.values(
            'menu_item__name'
        ).annotate(
            total_ordered=Sum('quantity')
        ).order_by('-total_ordered')[:5]

        #pending orders
        pending_orders = Order.objects.filter(
            status__in = ['paid', 'preparing']
        ).select_related('customer').prefetch_related(
            'items__menu_item'
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
            'popular_items': list(popular_items),
            'pending_orders': pending_serializer.data
        })


class CartView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        cart, created = Cart.objects.get_or_create(customer=request.user)
        serializer = CartSerializer(cart)
        return Response(serializer.data)

    def post(self, request):
        # add item to cart
        cart, created = Cart.objects.get_or_create(customer=request.user)
        menu_item_id = request.data.get('menu_item_id')
        quantity = int(request.data.get('quantity', 1))

        menu_item = MenuItem.objects.filter(
            id=menu_item_id, is_available=True).first()
        if not menu_item:
            return Response({'error': 'Menu item not found or unavailable'},
                            status=status.HTTP_404_NOT_FOUND)

        cart_item, created = CartItem.objects.get_or_create(
            cart=cart, menu_item=menu_item)
        if not created:
            cart_item.quantity += quantity
        else:
            cart_item.quantity = quantity
        cart_item.save()

        serializer = CartSerializer(cart)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request):
        # clear entire cart
        cart = Cart.objects.filter(customer=request.user).first()
        if cart:
            cart.items.all().delete()
        return Response({'message': 'Cart cleared'})


class CartItemView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, item_id):
        cart = Cart.objects.filter(customer=request.user).first()
        if not cart:
            return Response({'error': 'Cart not found'},
                            status=status.HTTP_404_NOT_FOUND)
        cart_item = CartItem.objects.filter(id=item_id, cart=cart).first()
        if not cart_item:
            return Response({'error': 'Item not found in cart'},
                            status=status.HTTP_404_NOT_FOUND)
        quantity = request.data.get('quantity')
        if not quantity or int(quantity) < 1:
            return Response({'error': 'Quantity must be at least 1'},
                            status=status.HTTP_400_BAD_REQUEST)
        cart_item.quantity = int(quantity)
        cart_item.save()
        serializer = CartSerializer(cart)
        return Response(serializer.data)

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
        serializer = CartSerializer(cart)
        return Response(serializer.data)


class OrderListView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        # admin and kitchen see all orders
        # customers see only their own
        if request.user.is_admin or request.user.is_kitchen:
            orders = Order.objects.select_related('customer').prefetch_related(
                'items__menu_item').all().order_by('-created_at')
        else:
            orders = Order.objects.select_related('customer').prefetch_related(
                'items__menu_item').filter(
                customer=request.user).order_by('-created_at')
        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request):
        # customers only
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
            for cart_item in cart.items.all():
                OrderItem.objects.create(
                    order=order,
                    menu_item=cart_item.menu_item,
                    quantity=cart_item.quantity,
                    price_at_purchase=cart_item.menu_item.price
                )
            # clear cart after order created
            cart.items.all().delete()

        serializer = OrderSerializer(order)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class OrderDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, order_id, user):
        try:
            order = Order.objects.select_related('customer').prefetch_related(
                'items__menu_item').get(id=order_id)
            # customers can only see their own orders
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
        # kitchen and admin can update order status
        if not request.user.is_kitchen and not request.user.is_admin:
            return Response(
                {'error': 'Only kitchen staff and admins can update order status'},
                status=status.HTTP_403_FORBIDDEN)

        order = self.get_object(order_id, request.user)
        if not order:
            return Response({'error': 'Order not found'},
                            status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get('status')
        valid_statuses = ['pending', 'paid', 'preparing', 'ready', 'collected', 'cancelled']
        if new_status not in valid_statuses:
            return Response({'error': f'Invalid status. Choose from {valid_statuses}'},
                            status=status.HTTP_400_BAD_REQUEST)

        order.status = new_status
        order.save()
        serializer = OrderSerializer(order)
        return Response(serializer.data)


class VerifyQRView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        # only kitchen and admin can verify QR codes
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
            return Response({'error': f'Order is not ready for collection. Current status: {order.status}'},
                            status=status.HTTP_400_BAD_REQUEST)

        order.status = 'collected'
        order.save()

        serializer = OrderSerializer(order)
        return Response({
            'message': 'Order collected successfully',
            'order': serializer.data
        }) 