from rest_framework import serializers

from .models import (Cart, CartItem, CartItemRiceExtra,
                     CartItemShawarmaExtra, CartItemDrink,
                     Order, OrderItem, OrderItemRiceExtra,
                     OrderItemShawarmaExtra, OrderItemDrink)
from menu.serializers import (CartMenuItemSerializer, MenuItemSizeSerializer,
                              RiceTypeSerializer, ShawarmaOptionSerializer,
                              RiceExtraSerializer, ShawarmaExtraSerializer,
                              DrinkSerializer)
from menu.models import (MenuItem, MenuItemSize, RiceType, ShawarmaOption,
                         RiceExtra, ShawarmaExtra, Drink)


def money(**kwargs):
    """
    Money is a string everywhere ("4000.00").

    Model DecimalFields already serialize that way; computed totals used to be
    SerializerMethodFields returning a raw Decimal, which the JSON encoder
    rendered as a bare number - so one payload carried both 4000.0 and
    "4000.00" for the same kind of value.
    """
    return serializers.DecimalField(
        max_digits=10, decimal_places=2, read_only=True, **kwargs)


class CartItemDrinkSerializer(serializers.ModelSerializer):
    drink = DrinkSerializer(read_only=True)
    drink_id = serializers.PrimaryKeyRelatedField(
        queryset=Drink.objects.all(), source='drink', write_only=True)

    class Meta:
        model = CartItemDrink
        fields = ['id', 'drink', 'drink_id', 'quantity']


class CartItemRiceExtraSerializer(serializers.ModelSerializer):
    extra = RiceExtraSerializer(read_only=True)
    extra_id = serializers.PrimaryKeyRelatedField(
        queryset=RiceExtra.objects.all(), source='extra', write_only=True)

    class Meta:
        model = CartItemRiceExtra
        fields = ['id', 'extra', 'extra_id', 'quantity']


class CartItemShawarmaExtraSerializer(serializers.ModelSerializer):
    extra = ShawarmaExtraSerializer(read_only=True)
    extra_id = serializers.PrimaryKeyRelatedField(
        queryset=ShawarmaExtra.objects.all(), source='extra', write_only=True)

    class Meta:
        model = CartItemShawarmaExtra
        fields = ['id', 'extra', 'extra_id', 'is_added']


class CartItemSerializer(serializers.ModelSerializer):
    menu_item = CartMenuItemSerializer(read_only=True)
    menu_item_id = serializers.PrimaryKeyRelatedField(
        queryset=MenuItem.objects.all(), source='menu_item', write_only=True)
    size = MenuItemSizeSerializer(read_only=True)
    size_id = serializers.PrimaryKeyRelatedField(
        queryset=MenuItemSize.objects.all(), source='size',
        write_only=True, required=False, allow_null=True)
    rice_type = RiceTypeSerializer(read_only=True)
    rice_type_id = serializers.PrimaryKeyRelatedField(
        queryset=RiceType.objects.all(), source='rice_type',
        write_only=True, required=False, allow_null=True)
    shawarma_option = ShawarmaOptionSerializer(read_only=True)
    shawarma_option_id = serializers.PrimaryKeyRelatedField(
        queryset=ShawarmaOption.objects.all(), source='shawarma_option',
        write_only=True, required=False, allow_null=True)
    rice_extras = CartItemRiceExtraSerializer(many=True, read_only=True)
    shawarma_extras = CartItemShawarmaExtraSerializer(many=True, read_only=True)
    drinks = CartItemDrinkSerializer(many=True, read_only=True)
    total = money(source='get_total')

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Drop only the keys the item's *type* rules out. `drinks` used to be
        # dropped whenever it happened to be empty, which made the response
        # shape vary with data rather than type - and the .exists() check that
        # decided it fired a query per line, defeating the prefetch.
        if instance.menu_item.item_type == 'shawarma':
            data.pop('size', None)
            data.pop('rice_type', None)
            data.pop('rice_extras', None)
        else:
            data.pop('shawarma_option', None)
            data.pop('shawarma_extras', None)

        return data

    class Meta:
        model = CartItem
        fields = [
            'id', 'menu_item', 'menu_item_id',
            'size', 'size_id',
            'rice_type', 'rice_type_id',
            'shawarma_option', 'shawarma_option_id',
            'quantity',
            'rice_extras', 'shawarma_extras', 'drinks',
            'total', 'created_at',
        ]
        read_only_fields = ['created_at']


class CartSerializer(serializers.ModelSerializer):
    items = CartItemSerializer(many=True, read_only=True)
    total = money(source='get_total')

    class Meta:
        model = Cart
        fields = ['id', 'items', 'total', 'updated_at']
        read_only_fields = ['updated_at']


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

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # Everything on an OrderItem is a frozen snapshot, so the line's type
        # is read back off the stored option name rather than the live menu.
        if instance.shawarma_option_name:
            data.pop('size_name', None)
            data.pop('size_price', None)
            data.pop('rice_type_name', None)
            data.pop('rice_extras', None)
        else:
            data.pop('shawarma_option_name', None)
            data.pop('shawarma_option_price', None)
            data.pop('shawarma_extras', None)

        return data

    class Meta:
        model = OrderItem
        fields = [
            'id', 'menu_item', 'menu_item_name',
            'size_name', 'size_price', 'rice_type_name',
            'shawarma_option_name', 'shawarma_option_price',
            'quantity', 'special_instructions', 'item_total',
            'rice_extras', 'shawarma_extras', 'drinks',
        ]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    customer_username = serializers.CharField(
        source='customer.username', read_only=True)

    class Meta:
        model = Order
        fields = [
            'id', 'customer', 'customer_username', 'status', 'total_amount',
            'pickup_time', 'qr_code', 'special_instructions', 'items',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'customer', 'total_amount', 'qr_code',
            'created_at', 'updated_at',
        ]
