from rest_framework import serializers
from .models import (Cart, CartItem, CartItemRiceExtra,
                     CartItemShawarmaExtra, CartItemDrink,
                     Order, OrderItem, OrderItemRiceExtra,
                     OrderItemShawarmaExtra, OrderItemDrink)
from menu.serializers import (MenuItemSerializer, MenuItemSizeSerializer,
                               RiceTypeSerializer, ShawarmaOptionSerializer,
                               RiceExtraSerializer, ShawarmaExtraSerializer,
                               DrinkSerializer)
from menu.models import MenuItemSize, RiceType, ShawarmaOption, RiceExtra, ShawarmaExtra, Drink


class CartItemDrinkSerializer(serializers.ModelSerializer):
    drink = DrinkSerializer(read_only=True)
    drink_id = serializers.PrimaryKeyRelatedField(
        queryset=Drink.objects.all(),
        source='drink',
        write_only=True
    )

    class Meta:
        model = CartItemDrink
        fields = ['id', 'drink', 'drink_id', 'quantity']


class CartItemRiceExtraSerializer(serializers.ModelSerializer):
    extra = RiceExtraSerializer(read_only=True)
    extra_id = serializers.PrimaryKeyRelatedField(
        queryset=RiceExtra.objects.all(),
        source='extra',
        write_only=True
    )

    class Meta:
        model = CartItemRiceExtra
        fields = ['id', 'extra', 'extra_id', 'quantity']

    def validate_quantity(self, value):
        return value


class CartItemShawarmaExtraSerializer(serializers.ModelSerializer):
    extra = ShawarmaExtraSerializer(read_only=True)
    extra_id = serializers.PrimaryKeyRelatedField(
        queryset=ShawarmaExtra.objects.all(),
        source='extra',
        write_only=True
    )

    class Meta:
        model = CartItemShawarmaExtra
        fields = ['id', 'extra', 'extra_id', 'is_added']


class CartItemSerializer(serializers.ModelSerializer):
    menu_item = MenuItemSerializer(read_only=True)
    menu_item_id = serializers.PrimaryKeyRelatedField(
        queryset=__import__('menu.models', fromlist=['MenuItem']).MenuItem.objects.all(),
        source='menu_item',
        write_only=True
    )
    size = MenuItemSizeSerializer(read_only=True)
    size_id = serializers.PrimaryKeyRelatedField(
        queryset=MenuItemSize.objects.all(),
        source='size',
        write_only=True,
        required=False,
        allow_null=True
    )
    rice_type = RiceTypeSerializer(read_only=True)
    rice_type_id = serializers.PrimaryKeyRelatedField(
        queryset=RiceType.objects.all(),
        source='rice_type',
        write_only=True,
        required=False,
        allow_null=True
    )
    shawarma_option = ShawarmaOptionSerializer(read_only=True)
    shawarma_option_id = serializers.PrimaryKeyRelatedField(
        queryset=ShawarmaOption.objects.all(),
        source='shawarma_option',
        write_only=True,
        required=False,
        allow_null=True
    )
    rice_extras = CartItemRiceExtraSerializer(many=True, read_only=True)
    shawarma_extras = CartItemShawarmaExtraSerializer(many=True, read_only=True)
    drinks = CartItemDrinkSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    def get_total(self, obj):
        return obj.get_total()

    class Meta:
        model = CartItem
        fields = [
            'id', 'menu_item', 'menu_item_id',
            'size', 'size_id',
            'rice_type', 'rice_type_id',
            'shawarma_option', 'shawarma_option_id',
            'quantity',
            'rice_extras', 'shawarma_extras', 'drinks',
            'total', 'created_at'
        ]
        read_only_fields = ['created_at']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = serializers.SerializerMethodField()

    def get_total(self, obj):
        return obj.get_total()

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class OrderItemRiceExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItemRiceExtra
        fields = ['id', 'extra_name', 'extra_price', 'quantity']


class OrderItemShawarmaExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItemShawarmaExtra
        fields = ['id', 'extra_name', 'extra_price', 'is_added']


class OrderItemDrinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = OrderItemDrink
        fields = ['id', 'drink_name', 'drink_price', 'quantity']


class OrderItemSerializer(serializers.ModelSerializer):
    rice_extras = OrderItemRiceExtraSerializer(many=True, read_only=True)
    shawarma_extras = OrderItemShawarmaExtraSerializer(many=True, read_only=True)
    drinks = OrderItemDrinkSerializer(many=True, read_only=True)

    class Meta:
        model = OrderItem
        fields = [
            'id', 'menu_item', 'size_name', 'size_price',
            'rice_type_name', 'shawarma_option_name',
            'shawarma_option_price', 'quantity', 'item_total',
            'rice_extras', 'shawarma_extras', 'drinks'
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'status', 'total_amount',
            'pickup_time', 'qr_code', 'items',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'customer', 'total_amount', 'qr_code',
            'created_at', 'updated_at'
        ]