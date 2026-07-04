from rest_framework import serializers
from .models import Category, MenuItem

class CategorySerializer(serializers.ModelSerializer):
    items = serializers.SerializerMethodField()
    class Meta:
        model = Category
        fields = ['id', 'name', 'is_active','items']

class MenuItemSerializer(serializers.ModelSerializer):
    category = CategorySerializer(read_only = True)

    class Meta:
        model = MenuItem
        fields = ['id', 'category','name','description','price',
                  'image','is_available','updated_at', 'created_at']
        read_only_fields = ['created_at', 'updated_at']