from rest_framework import serializers
from .models import Category, MenuItem


class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category.name', read_only=True)
    image_url = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

    class Meta:
        model = MenuItem
        fields = ['id', 'category', 'category_name', 'name', 'description',
                  'price', 'image', 'image_url', 'is_available',
                  'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {'image': {'write_only': True}}


class CategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()

    def get_items(self, obj):
        available_items = obj.items.filter(is_available=True)
        return MenuItemSerializer(available_items, many=True).data

    class Meta:
        model = Category
        fields = ['id', 'name', 'is_active', 'items']