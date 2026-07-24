from django.db import transaction
from rest_framework import status
from rest_framework import serializers as drf_serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from order.models import Order
from order.serializers import OrderSerializer
from drf_spectacular.utils import extend_schema, inline_serializer

class VerifyQRView(APIView):
    permission_classes = [IsAuthenticated]


    @extend_schema(
            request=inline_serializer(name='VerifyQR',
                                      fields={
                                          'qr_code':drf_serializers.CharField})
    )
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