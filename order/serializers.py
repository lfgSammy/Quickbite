from rest_framework import serializers
from .models import Order, OrderItem, Cart, CartItem
from menu.serializers import MenuItemSerializer
from users.serializers import UserSerializer


class CartItemSerializer(serializers.ModelSerializer):
    menu_item = MenuItemSerializer(read_only=True)
    menu_item_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__('menu.models', fromlist=['MenuItem']).MenuItem.objects.all(),
        source='menu_item',
        write_only=True
    )
    total = serializers.SerializerMethodField()

    def get_total(self, obj):
        return obj.get_total()

    class Meta:
        model = CartItem
        fields = ['id', 'menu_item', 'menu_item_id', 'quantity', 'total']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    def get_total(self, obj):
        return obj.get_total()

    class Meta:
        model = Cart
        fields = ['id', 'customer', 'items', 'total', 'created_at', 'updated_at']
        read_only_fields = ['customer', 'created_at', 'updated_at']


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item = MenuItemSerializer(read_only=True)

    class Meta:
        model = OrderItem
        fields = ['id', 'menu_item', 'quantity', 'price_at_purchase']


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer = UserSerializer(read_only=True)

    class Meta:
        model = Order
        fields = ['id', 'customer', 'status', 'total_amount', 'pickup_time',
                  'qr_code', 'items', 'created_at', 'updated_at']
        read_only_fields = ['customer', 'qr_code', 'total_amount',
                            'created_at', 'updated_at']