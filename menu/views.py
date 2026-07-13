from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import MenuItem, RiceType, RiceExtra, ShawarmaExtra, Drink
from .serializers import (MenuItemSerializer, RiceTypeSerializer,
                           RiceExtraSerializer, ShawarmaExtraSerializer,
                           DrinkSerializer)


class MenuItemListView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        items = MenuItem.objects.prefetch_related(
            'sizes', 'shawarma_options'
        ).filter(is_available=True)
        serializer = MenuItemSerializer(items, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can add menu items'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = MenuItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MenuItemDetailView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_object(self, pk):
        try:
            return MenuItem.objects.prefetch_related(
                'sizes', 'shawarma_options').get(pk=pk)
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
        if not request.user.is_admin_user:
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
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can delete menu items'},
                            status=status.HTTP_403_FORBIDDEN)
        item = self.get_object(pk)
        if not item:
            return Response({'error': 'Menu item not found'},
                            status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RiceTypeListView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        rice_types = RiceType.objects.all()
        serializer = RiceTypeSerializer(rice_types, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can add rice types'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = RiceTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RiceExtraListView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        extras = RiceExtra.objects.filter(is_available=True)
        serializer = RiceExtraSerializer(extras, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can add extras'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = RiceExtraSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RiceExtraDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self, pk):
        try:
            return RiceExtra.objects.get(pk=pk)
        except RiceExtra.DoesNotExist:
            return None

    def patch(self, request, pk):
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can update extras'},
                            status=status.HTTP_403_FORBIDDEN)
        extra = self.get_object(pk)
        if not extra:
            return Response({'error': 'Extra not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = RiceExtraSerializer(extra, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ShawarmaExtraListView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        extras = ShawarmaExtra.objects.filter(is_available=True)
        serializer = ShawarmaExtraSerializer(extras, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can add shawarma extras'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = ShawarmaExtraSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ShawarmaExtraDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can update shawarma extras'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            extra = ShawarmaExtra.objects.get(pk=pk)
        except ShawarmaExtra.DoesNotExist:
            return Response({'error': 'Extra not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = ShawarmaExtraSerializer(extra, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DrinkListView(APIView):
    def get_permissions(self):
        if self.request.method == 'GET':
            return [AllowAny()]
        return [IsAuthenticated()]

    def get(self, request):
        drinks = Drink.objects.filter(is_available=True)
        serializer = DrinkSerializer(drinks, many=True)
        return Response(serializer.data)

    def post(self, request):
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can add drinks'},
                            status=status.HTTP_403_FORBIDDEN)
        serializer = DrinkSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DrinkDetailView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, pk):
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can update drinks'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            drink = Drink.objects.get(pk=pk)
        except Drink.DoesNotExist:
            return Response({'error': 'Drink not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = DrinkSerializer(drink, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        if not request.user.is_admin_user:
            return Response({'error': 'Only admins can delete drinks'},
                            status=status.HTTP_403_FORBIDDEN)
        try:
            drink = Drink.objects.get(pk=pk)
        except Drink.DoesNotExist:
            return Response({'error': 'Drink not found'},
                            status=status.HTTP_404_NOT_FOUND)
        drink.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)