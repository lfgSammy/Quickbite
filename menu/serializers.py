from rest_framework import serializers
from .models import (MenuItem, MenuItemSize, RiceType,
                     ShawarmaOption, RiceExtra, ShawarmaExtra, Drink)

class RiceTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RiceType
        fields = ['id', 'name']

class MenuItemSizeSerializer(serializers.ModelSerializer):
    class Meta:
        model = MenuItemSize
        fields = ['id', 'name', 'price']

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

class DrinkSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

    class Meta:
        model = Drink
        fields = ['id', 'name', 'price', 'image', 'image_url', 'is_available']
        extra_kwargs = {'image': {'write_only': True}}

class MenuItemSerializer(serializers.ModelSerializer):
    sizes = MenuItemSizeSerializer(many=True, read_only=True)
    shawarma_options = ShawarmaOptionSerializer(many=True, read_only=True)
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

    class Meta:
        model = MenuItem
        fields = ['id', 'name', 'description', 'image', 'image_url',
                  'item_type', 'is_available', 'sizes',
                  'shawarma_options', 'created_at', 'updated_at']
        extra_kwargs = {'image': {'write_only': True}}
        read_only_fields = ['created_at', 'updated_at']