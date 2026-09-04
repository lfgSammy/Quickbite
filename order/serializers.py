from decimal import Decimal

from django.utils import timezone
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
    """Read-only view of a cart line. Writes go through the serializers below."""

    menu_item = CartMenuItemSerializer(read_only=True)
    size = MenuItemSizeSerializer(read_only=True)
    rice_type = RiceTypeSerializer(read_only=True)
    shawarma_option = ShawarmaOptionSerializer(read_only=True)
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
            'id', 'menu_item', 'size', 'rice_type', 'shawarma_option',
            'quantity', 'rice_extras', 'shawarma_extras', 'drinks',
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


# --------------------------------------------------------------------------
# Write serializers
#
# The cart views used to re-read request.data by hand and validate inline,
# which meant the rules were duplicated between "add to cart" and "update
# cart item", and anything unrecognised (a bad extra_id, a sold-out drink)
# was silently skipped while still returning 201. These carry the rules once
# and reject bad input instead of dropping it.
# --------------------------------------------------------------------------


class RiceExtraInputSerializer(serializers.Serializer):
    extra_id = serializers.PrimaryKeyRelatedField(
        queryset=RiceExtra.objects.all(), source='extra')
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        extra, quantity = attrs['extra'], attrs['quantity']
        if not extra.is_available:
            raise serializers.ValidationError(
                f'{extra.name} is not available right now.')
        # Previously clamped to max_quantity in silence, so the customer was
        # charged for fewer than they asked for without being told.
        if quantity > extra.max_quantity:
            raise serializers.ValidationError(
                f'You can add at most {extra.max_quantity} x {extra.name}.')
        return attrs


class ShawarmaExtraInputSerializer(serializers.Serializer):
    extra_id = serializers.PrimaryKeyRelatedField(
        queryset=ShawarmaExtra.objects.all(), source='extra')
    is_added = serializers.BooleanField(default=True)

    def validate(self, attrs):
        extra = attrs['extra']
        if attrs['is_added'] and not extra.is_available:
            raise serializers.ValidationError(
                f'{extra.name} is not available right now.')
        return attrs


class DrinkInputSerializer(serializers.Serializer):
    drink_id = serializers.PrimaryKeyRelatedField(
        queryset=Drink.objects.all(), source='drink')
    quantity = serializers.IntegerField(min_value=1, default=1)

    def validate(self, attrs):
        drink = attrs['drink']
        if not drink.is_available:
            raise serializers.ValidationError(
                f'{drink.name} is not available right now.')
        return attrs


class CartLineWriteMixin:
    """Shared rules and child-row writing for the create and update paths."""

    def check_choices_match_item(self, menu_item, attrs, require_choice):
        """
        Enforce the rules implied by the item's type.

        `require_choice` is True on create (you must pick a size or an option)
        and False on update, where the existing line already has one.
        """
        item_type = menu_item.item_type

        if item_type not in ('rice', 'shawarma'):
            raise serializers.ValidationError(
                {'menu_item_id':
                 'This item is not configured for ordering yet.'})

        if item_type == 'rice':
            size = attrs.get('size')
            if require_choice and not size:
                raise serializers.ValidationError(
                    {'size_id': 'Size is required for rice items.'})
            if size:
                if size.menu_item_id != menu_item.id:
                    raise serializers.ValidationError(
                        {'size_id':
                         'That size belongs to a different menu item.'})
                if not size.is_available:
                    raise serializers.ValidationError(
                        {'size_id':
                         f'{size.name} is not available right now.'})
            if attrs.get('shawarma_option'):
                raise serializers.ValidationError(
                    {'shawarma_option_id':
                     'A rice item cannot take a shawarma option.'})
            if attrs.get('shawarma_extras'):
                raise serializers.ValidationError(
                    {'shawarma_extras':
                     'Shawarma extras cannot be added to a rice item.'})
        else:
            option = attrs.get('shawarma_option')
            if require_choice and not option:
                raise serializers.ValidationError(
                    {'shawarma_option_id': 'Shawarma option is required.'})
            if option:
                if option.menu_item_id != menu_item.id:
                    raise serializers.ValidationError(
                        {'shawarma_option_id':
                         'That option belongs to a different menu item.'})
                if not option.is_available:
                    raise serializers.ValidationError(
                        {'shawarma_option_id':
                         f'{option.name} is not available right now.'})
            if attrs.get('size'):
                raise serializers.ValidationError(
                    {'size_id': 'A shawarma item does not take a size.'})
            if attrs.get('rice_extras'):
                raise serializers.ValidationError(
                    {'rice_extras':
                     'Rice extras cannot be added to a shawarma item.'})

    def write_children(self, cart_item, validated_data, replace):
        """Create the extra/drink rows. On update, replace them wholesale."""
        specs = (
            ('rice_extras', CartItemRiceExtra,
             lambda row: {'extra': row['extra'],
                          'quantity': row['quantity']}),
            ('shawarma_extras', CartItemShawarmaExtra,
             lambda row: {'extra': row['extra'],
                          'is_added': row['is_added']}),
            ('drinks', CartItemDrink,
             lambda row: {'drink': row['drink'],
                          'quantity': row['quantity']}),
        )
        for field, model, build_kwargs in specs:
            rows = validated_data.get(field)
            if rows is None:
                continue
            if replace:
                getattr(cart_item, field).all().delete()
            for row in rows:
                model.objects.create(cart_item=cart_item, **build_kwargs(row))


class CartItemCreateSerializer(CartLineWriteMixin, serializers.Serializer):
    menu_item_id = serializers.PrimaryKeyRelatedField(
        queryset=MenuItem.objects.all(), source='menu_item')
    quantity = serializers.IntegerField(min_value=1, default=1)
    size_id = serializers.PrimaryKeyRelatedField(
        queryset=MenuItemSize.objects.all(), source='size',
        required=False, allow_null=True)
    rice_type_id = serializers.PrimaryKeyRelatedField(
        queryset=RiceType.objects.all(), source='rice_type',
        required=False, allow_null=True)
    shawarma_option_id = serializers.PrimaryKeyRelatedField(
        queryset=ShawarmaOption.objects.all(), source='shawarma_option',
        required=False, allow_null=True)
    rice_extras = RiceExtraInputSerializer(many=True, required=False)
    shawarma_extras = ShawarmaExtraInputSerializer(many=True, required=False)
    drinks = DrinkInputSerializer(many=True, required=False)

    def validate_menu_item_id(self, menu_item):
        if not menu_item.is_available:
            raise serializers.ValidationError(
                f'{menu_item.name} is not available right now.')
        return menu_item

    def validate(self, attrs):
        self.check_choices_match_item(attrs['menu_item'], attrs, True)
        return attrs

    def create(self, validated_data):
        cart_item = CartItem.objects.create(
            cart=validated_data['cart'],
            menu_item=validated_data['menu_item'],
            size=validated_data.get('size'),
            rice_type=validated_data.get('rice_type'),
            shawarma_option=validated_data.get('shawarma_option'),
            quantity=validated_data['quantity'],
        )
        self.write_children(cart_item, validated_data, replace=False)
        return cart_item


class CartItemUpdateSerializer(CartLineWriteMixin, serializers.Serializer):
    """
    Partial update of an existing line.

    The menu item and its size/option are fixed once the line exists - change
    those by removing the line and adding it again.
    """

    quantity = serializers.IntegerField(min_value=1, required=False)
    rice_extras = RiceExtraInputSerializer(many=True, required=False)
    shawarma_extras = ShawarmaExtraInputSerializer(many=True, required=False)
    drinks = DrinkInputSerializer(many=True, required=False)

    def validate(self, attrs):
        self.check_choices_match_item(
            self.instance.menu_item, attrs, False)
        return attrs

    def update(self, instance, validated_data):
        if 'quantity' in validated_data:
            instance.quantity = validated_data['quantity']
            instance.save(update_fields=['quantity'])
        self.write_children(instance, validated_data, replace=True)
        return instance


class OrderCreateSerializer(serializers.Serializer):
    """
    Everything that has to be true before an order can be placed.

    This was ~45 lines of request.data.get() and inline checks in the view.
    Gathering it here means the rules are in one place and the API docs can
    finally describe what this endpoint accepts.
    """

    pickup_time = serializers.DateTimeField()
    special_instructions = serializers.CharField(
        required=False, allow_blank=True, max_length=500)

    def validate_pickup_time(self, pickup_time):
        from users.models import OperatingHours

        if timezone.is_naive(pickup_time):
            pickup_time = timezone.make_aware(pickup_time)

        if pickup_time <= timezone.now():
            raise serializers.ValidationError(
                'Pickup time must be in the future.')

        # Checked against the hours for the *pickup* day, not today's - a
        # Saturday order for Sunday pickup was being judged on Saturday's.
        local = timezone.localtime(pickup_time)
        hours = OperatingHours.objects.filter(day=local.weekday()).first()

        if not hours or not hours.is_open:
            raise serializers.ValidationError(
                f'We are closed on {local.strftime("%A")}.')

        if not (hours.open_time <= local.time() <= hours.close_time):
            raise serializers.ValidationError(
                f'Pickup must be between '
                f'{hours.open_time.strftime("%I:%M %p")} and '
                f'{hours.close_time.strftime("%I:%M %p")} on '
                f'{local.strftime("%A")}.')

        return pickup_time

    def validate(self, attrs):
        cart = self.context['cart']

        lines = list(cart.items.select_related(
            'menu_item', 'size', 'rice_type', 'shawarma_option'
        ).prefetch_related(
            'rice_extras__extra', 'shawarma_extras__extra', 'drinks__drink',
        ))

        if not lines:
            raise serializers.ValidationError('Your cart is empty.')

        # A line can go stale between adding it and checking out: the dish
        # pulled from the menu, or its size deleted, which would otherwise
        # price the line at zero and freeze that into a real order.
        for line in lines:
            if not line.menu_item.is_available:
                raise serializers.ValidationError(
                    f'{line.menu_item.name} is no longer available. '
                    f'Please update your cart.')
            if line.get_base_price() <= 0:
                raise serializers.ValidationError(
                    f'The option you chose for {line.menu_item.name} is no '
                    f'longer available. Please update your cart.')

        attrs['lines'] = lines
        return attrs

    def create(self, validated_data):
        cart = self.context['cart']
        lines = validated_data['lines']

        order = Order.objects.create(
            customer=cart.customer,
            pickup_time=validated_data['pickup_time'],
            special_instructions=validated_data.get(
                'special_instructions', ''),
            total_amount=sum(
                (line.get_total() for line in lines), Decimal('0.00')),
            status='pending',
        )

        for line in lines:
            order_item = OrderItem.objects.create(
                order=order,
                menu_item=line.menu_item,
                menu_item_name=line.menu_item.name,
                size_name=line.size.name if line.size else '',
                size_price=line.size.price if line.size else 0,
                rice_type_name=(
                    line.rice_type.name if line.rice_type else ''),
                shawarma_option_name=(
                    line.shawarma_option.name if line.shawarma_option else ''),
                shawarma_option_price=(
                    line.shawarma_option.price if line.shawarma_option else 0),
                quantity=line.quantity,
                item_total=line.get_total(),
            )

            # Prices are copied, not referenced: an order is a record of what
            # was charged, so later menu edits must not rewrite history.
            for rice_extra in line.rice_extras.all():
                OrderItemRiceExtra.objects.create(
                    order_item=order_item,
                    extra_name=rice_extra.extra.name,
                    extra_price=rice_extra.extra.price,
                    quantity=rice_extra.quantity,
                )
            for shawarma_extra in line.shawarma_extras.all():
                OrderItemShawarmaExtra.objects.create(
                    order_item=order_item,
                    extra_name=shawarma_extra.extra.name,
                    extra_price=shawarma_extra.extra.price,
                    is_added=shawarma_extra.is_added,
                )
            for drink in line.drinks.all():
                OrderItemDrink.objects.create(
                    order_item=order_item,
                    drink_name=drink.drink.name,
                    drink_price=drink.drink.price,
                    quantity=drink.quantity,
                )

        cart.items.all().delete()
        return order


class OrderStatusSerializer(serializers.Serializer):
    """
    Kitchen-driven status changes.

    `collected` is deliberately absent: an order only reaches it by having its
    QR code scanned, so it cannot be set by hand here.
    """

    SETTABLE = ['preparing', 'ready', 'cancelled']
    # A status change is only meaningful once the order has been paid for.
    CHANGEABLE_FROM = ['paid', 'preparing']

    status = serializers.ChoiceField(choices=SETTABLE)

    def validate(self, attrs):
        current = self.instance.status
        if current not in self.CHANGEABLE_FROM:
            raise serializers.ValidationError(
                f'An order that is {current} can no longer be updated.')
        return attrs

    def update(self, instance, validated_data):
        instance.status = validated_data['status']
        instance.save(update_fields=['status', 'updated_at'])
        return instance


class RevertOrderResponseSerializer(serializers.Serializer):
    """Reverting an order cancels it and hands the cart back."""

    message = serializers.CharField()
    cart = CartSerializer()


class VerifyQRResponseSerializer(serializers.Serializer):
    """A successful scan marks the order collected and echoes it back."""

    message = serializers.CharField()
    order = OrderSerializer()


class DashboardOverviewSerializer(serializers.Serializer):
    total_orders = serializers.IntegerField()
    today_orders = serializers.IntegerField()
    total_revenue = money()
    today_revenue = money()
    weekly_revenue = money()


class DashboardStatusCountSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()


class AdminDashboardSerializer(serializers.Serializer):
    overview = DashboardOverviewSerializer()
    status_breakdown = DashboardStatusCountSerializer(many=True)
    pending_orders = OrderSerializer(many=True)


class VerifyQRRequestSerializer(serializers.Serializer):
    qr_code = serializers.CharField()
