import hmac
import hashlib
import requests
from django.conf import settings
from django.utils import timezone
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from .models import Payment
from .serializers import PaymentSerializer
from order.models import Order
from users.models import Notification

class initializePaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        order_id = request.data.get('order_id')

        order = Order.objects.filter(
            id=order_id, customer= request.user).first()
        if not order:
            return Response({'error':'No order found'}, status=status.HTTP_404_NOT_FOUND)
        if order.status != 'pending':
            return Response({'error':'Order is not pending payment'},
                            status=status.HTTP_400_BAD_REQUEST)
        #initialize payment with paystack
        url = 'https://api.paystack.co/transaction/initialize'
        headers = {
            "Authorization":f'Bearer {settings.PAYSTACK_SECRET_KEY}',
            "Content-Type":'application/json'
        }

        data = {
            'email':request.user.email,
            'amount':int(order.total_amount*100), #paystack uses kobo
            'reference':f'order_{order.id}_{order.qr_code}',
            'metadata':{
                'order_id':order.id,
                'customer':request.user.username
            }
        }

        response = request.post(url, json=data, headers=headers)
        response_data = response.json()

        if not response_data.get('status'):
            return Response({'error':'Payment initialization failed'},
                            status=status.HTTP_400_BAD_REQUEST)
        
        #create pending payment records
        Payment.objects.create(
            order = order,
            paystack_reference = response_data['data']['reference'],
            amount = order.total_amount,
            status = 'pending'
        )

        return Response({
            'payment_url':response_data['data']['authorization_url'],
            'reference':response_data['data']['reference']
        })
        
class VerifyPaymentView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        reference = request.data.get('reference')
        if not reference:
            return Response({'error': 'Reference is required'},
                            status=status.HTTP_400_BAD_REQUEST)

        # verify with Paystack
        url = f'https://api.paystack.co/transaction/verify/{reference}'
        headers = {
            'Authorization': f'Bearer {settings.PAYSTACK_SECRET_KEY}'
        }
        response = requests.get(url, headers=headers)
        response_data = response.json()

        if not response_data.get('status'):
            return Response({'error': 'Verification failed'},
                            status=status.HTTP_400_BAD_REQUEST)

        paystack_data = response_data['data']

        payment = Payment.objects.filter(
            paystack_reference=reference).first()
        if not payment:
            return Response({'error': 'Payment record not found'},
                            status=status.HTTP_404_NOT_FOUND)

        if paystack_data['status'] == 'success':
            payment.status = 'success'
            payment.verified_at = timezone.now()
            payment.save()

            # update order status
            order = payment.order
            order.status = 'paid'
            order.save()

            # notify customer
            Notification.objects.create(
                user=order.customer,
                message=f'Payment confirmed for Order #{order.id}. '
                        f'Your QR code: {order.qr_code}. '
                        f'Pickup time: {order.pickup_time}'
            )

            serializer = PaymentSerializer(payment)
            return Response({
                'message': 'Payment verified successfully',
                'payment': serializer.data,
                'qr_code': str(order.qr_code),
                'order_id': order.id
            })

        payment.status = 'failed'
        payment.save()
        return Response({'error': 'Payment was not successful'},
                        status=status.HTTP_400_BAD_REQUEST)
    
class PaystackWebhookView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        # verify webhook signature
        paystack_signature = request.headers.get('x-paystack-signature')
        computed_signature = hmac.new(
            settings.PAYSTACK_SECRET_KEY.encode('utf-8'),
            request.body,
            hashlib.sha512
        ).hexdigest()

        if paystack_signature != computed_signature:
            return Response({'error': 'Invalid signature'},
                            status=status.HTTP_400_BAD_REQUEST)

        event = request.data.get('event')
        data = request.data.get('data', {})

        if event == 'charge.success':
            reference = data.get('reference')
            payment = Payment.objects.filter(
                paystack_reference=reference).first()
            if payment and payment.status != 'success':
                payment.status = 'success'
                payment.verified_at = timezone.now()
                payment.save()

                order = payment.order
                order.status = 'paid'
                order.save()

                Notification.objects.create(
                    user=order.customer,
                    message=f'Payment confirmed for Order #{order.id}. '
                            f'Your QR code: {order.qr_code}'
                )

        return Response({'status': 'ok'})