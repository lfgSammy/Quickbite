from rest_framework import serializers
from .models import (MenuItem, MenuItemSize, RiceType,
                     ShawarmaOption, RiceExtra, ShawarmaExtra, Drink)


class ImageUrlMixin:
    """Cloudinary URL for a model with an `image` field, or None."""

    def get_image_url(self, obj):
        return obj.image.url if obj.image else None


class RiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiceType
        fields = ['id', 'name']


class MenuItemSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemSize
        fields = ['id', 'name', 'price', 'is_available']


class ShawarmaOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShawarmaOption
        fields = ['id', 'name', 'price', 'is_available']


class RiceExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiceExtra
        fields = ['id', 'name', 'price', 'is_available', 'max_quantity']


class ShawarmaExtraSerializer(serializers.ModelSerializer):
    class Meta:
        model = ShawarmaExtra
        fields = ['id', 'name', 'price', 'is_available']


class DrinkSerializer(ImageUrlMixin, serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    class Meta:
        model = Drink
        fields = ['id', 'name', 'price', 'image', 'image_url', 'is_available']
        extra_kwargs = {'image': {'write_only': True}}


class MenuItemSerializer(ImageUrlMixin, serializers.ModelSerializer):
    sizes = MenuItemSizeSerializer(many=True, read_only=True)
    shawarma_options = ShawarmaOptionSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()

    def to_representation(self, instance):
        data = super().to_representation(instance)

        # item_type is a real discriminator, not just a label: a rice item has
        # no shawarma options and never will. Returning an always-empty array
        # for the other type is noise, so drop the key that cannot apply.
        #
        # (This used to be attempted with get_sizes/get_shawarma_options
        # methods, but those never ran - `sizes` and `shawarma_options` are
        # declared as nested serializers, and get_<field> is only consulted by
        # SerializerMethodField. So both keys were always emitted, and the
        # is_available filter below never happened.)
        if instance.item_type == 'shawarma':
            data.pop('sizes', None)
            data['shawarma_options'] = [
                option for option in data.get('shawarma_options', [])
                if option['is_available']
            ]
        else:
            data.pop('shawarma_options', None)
            data['sizes'] = [
                size for size in data.get('sizes', []) if size['is_available']
            ]

        return data

    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'description', 'image', 'image_url',
                  'item_type', 'is_available', 'sizes', 'shawarma_options']
        extra_kwargs = {'image': {'write_only': True}}


class CartMenuItemSerializer(ImageUrlMixin, serializers.ModelSerializer):
    """
    The handful of menu fields a cart or order line actually needs.

    Cart lines used to embed the full MenuItemSerializer - every size, every
    option, both timestamps - for an item the customer had already chosen an
    option from. The frontend reads exactly `name` off it.
    """

    image_url = serializers.SerializerMethodField()

    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'image_url', 'item_type']
