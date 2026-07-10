from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from .models import Category, MenuItem
from .serializers import CategorySerializer, MenuItemSerializer

class CategoryListView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get(self, request):
        categories = Category.objects.filter(is_active=True).prefetch_related('items')
        serializer = CategorySerializer(categories, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        if not request.user.is_admin_user:
            return Response({'error':'Only admins can create categories'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = CategorySerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data,status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class CategoryDetailView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get_objects(self, pk):
        try:
            return Category.objects.get(pk=pk)
        except Category.DoesNotExist:
            return None 
        
    def get(self, request, pk):
        category = self.get_objects(pk)
        if not category:
            return Response({'error':'Category not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = CategorySerializer(category)
        return Response(serializer.data)
    
    def patch(self, request, pk):
        if not request.user.is_admin_user:
            return Response({'error':'Only admins can update categories'},
                            status=status.HTTP_403_FORBIDDEN)
        category = self.get_objects(pk)
        if not category:
            return Response({'error':'Category not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = CategorySerializer(category, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self,request,pk):
        if not request.user.is_admin_user:
            return Response({'error':'Only admins can delete categories'},
                            status=status.HTTP_403_FORBIDDEN)
        category = self.get_objects(pk)
        if not category:
            return Response({'error':'Category not found'}, status=status.HTTP_404_NOT_FOUND)
        category.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
class MenuItemListView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    
    def get(self, request):
        items = MenuItem.objects.select_related('category').filter(is_available=True)
        #filter by category
        category_id = request.query_params.get('category')
        if category_id:
            items = items.filter(category_id=category_id)
        #search by name
        search = request.query_params.get('search')
        if search:
            items = items.filter(name__icontains=search)
        serializer = MenuItemSerializer(items, many=True)
        return Response(serializer.data)
    
    def post(self, request):
        if not request.user.is_admin_user:
            return Response({'error':'Only admins can add menu items'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = MenuItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
class MenuItemDetailView(APIView):
    def get_permissions(self):
        if self.request.method =='GET':
            return [AllowAny()]
        return [IsAuthenticated()]
    def get_object(self, pk):
        try:
            return MenuItem.objects.select_related('category').get(pk=pk)
        except MenuItem.DoesNotExist:
            return None

    def get(self, request, pk):
        item = self.get_object(pk)
        if not item:
            return Response({'error': 'Menu item not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = MenuItemSerializer(item)
        return Response(serializer.data)

    def patch(self, request, pk):
        if not request.user.is_admin:
            return Response({'error': 'Only admins can update menu items'},
                            status=status.HTTP_403_FORBIDDEN)
        item = self.get_object(pk)
        if not item:
            return Response({'error': 'Menu item not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = MenuItemSerializer(item, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.is_admin:
            return Response({'error': 'Only admins can delete menu items'},
                            status=status.HTTP_403_FORBIDDEN)
        item = self.get_object(pk)
        if not item:
            return Response({'error': 'Menu item not found'},
                            status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)