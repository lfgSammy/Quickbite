from rest_framework import serializers
from .models import Category, MenuItem

class CategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    class Meta:
        model = Category
        fields = ['id', 'name', 'is_active','items']

class MenuItemSerializer(serializers.ModelSerializer):
    category_name = serializers.CharField(source='category_name', read_only='True')
    image_field = serializers.SerializerMethodField()

    def get_image_url(self, obj):
        if obj.image:
            return obj.image.url
        return None

    class Meta:
        model = MenuItem
        fields = ['id', 'category','name','category_name', 'description','price',
                  'image','image_url','is_available','updated_at', 'created_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'image':{'write_only':True}
        }