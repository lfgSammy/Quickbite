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