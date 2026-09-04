from rest_framework import serializers
from .models import Payment
from order.serializers import OrderSerializer

class PaymentSerializer(serializers.ModelSerializer):
    order = OrderSerializer(read_only= True)
    class Meta:
        model = Payment
        fields = ['id','order','paystack_reference', 'amount',
                  'status','verified_at', 'created_at']
        read_only_fields = ['paystack_reference', 'verified_at', 'created_at']

class InitializePaymentRequestSerializer(serializers.Serializer):
    order_id = serializers.IntegerField()


class InitializePaymentResponseSerializer(serializers.Serializer):
    """Where to send the customer, and the reference to verify afterwards."""

    payment_url = serializers.URLField()
    reference = serializers.CharField()


class VerifyPaymentRequestSerializer(serializers.Serializer):
    reference = serializers.CharField()


class VerifyPaymentResponseSerializer(serializers.Serializer):
    message = serializers.CharField()
    payment = PaymentSerializer()
    qr_code = serializers.CharField()
    order_id = serializers.IntegerField()


class WebhookAckSerializer(serializers.Serializer):
    """Paystack only needs a 200 with an acknowledgement."""

    status = serializers.CharField()
