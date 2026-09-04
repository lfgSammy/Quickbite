from rest_framework import status
from Quickbite.permissions import IsAdminOrReadOnly
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import (MenuItem, MenuItemSize, ShawarmaOption, RiceType,
                     RiceExtra, ShawarmaExtra, Drink)
from .serializers import (MenuItemSerializer, MenuItemSizeSerializer,
                           ShawarmaOptionSerializer, RiceTypeSerializer,
                           RiceExtraSerializer, ShawarmaExtraSerializer,
                           DrinkSerializer)
from drf_spectacular.utils import extend_schema

class MenuItemListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        items = MenuItem.objects.prefetch_related(
            'sizes', 'shawarma_options'
        ).filter(is_available=True)

        search = request.query_params.get('search')
        if search:
            items = items.filter(name__icontains=search)

        serializer = MenuItemSerializer(items, many=True)
        return Response(serializer.data)

    @extend_schema(request=MenuItemSerializer)
    def post(self, request):
        serializer = MenuItemSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class MenuItemDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

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

    @extend_schema(request=MenuItemSerializer)
    def patch(self, request, pk):
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
        item = self.get_object(pk)
        if not item:
            return Response({'error': 'Menu item not found'},
                            status=status.HTTP_404_NOT_FOUND)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class MenuItemSizeListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request, menu_item_id):
        sizes = MenuItemSize.objects.filter(menu_item_id=menu_item_id)
        serializer = MenuItemSizeSerializer(sizes, many=True)
        return Response(serializer.data)

    @extend_schema(request=MenuItemSizeSerializer)
    def post(self, request, menu_item_id):
        menu_item = MenuItem.objects.filter(
            id=menu_item_id, item_type='rice').first()
        if not menu_item:
            return Response({'error': 'Rice menu item not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = MenuItemSizeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(menu_item=menu_item)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class MenuItemSizeDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get_object(self, pk):
        try:
            return MenuItemSize.objects.get(pk=pk)
        except MenuItemSize.DoesNotExist:
            return None

    @extend_schema(request=MenuItemSizeSerializer)
    def patch(self, request, pk):
        size = self.get_object(pk)
        if not size:
            return Response({'error': 'Size not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = MenuItemSizeSerializer(size, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        size = self.get_object(pk)
        if not size:
            return Response({'error': 'Size not found'},
                            status=status.HTTP_404_NOT_FOUND)
        size.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShawarmaOptionListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request, menu_item_id):
        options = ShawarmaOption.objects.filter(menu_item_id=menu_item_id)
        serializer = ShawarmaOptionSerializer(options, many=True)
        return Response(serializer.data)

    @extend_schema(request=ShawarmaOptionSerializer)
    def post(self, request, menu_item_id):
        menu_item = MenuItem.objects.filter(
            id=menu_item_id, item_type='shawarma').first()
        if not menu_item:
            return Response({'error': 'Shawarma menu item not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = ShawarmaOptionSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save(menu_item=menu_item)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ShawarmaOptionDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get_object(self, pk):
        try:
            return ShawarmaOption.objects.get(pk=pk)
        except ShawarmaOption.DoesNotExist:
            return None

    @extend_schema(request=ShawarmaOptionSerializer)
    def patch(self, request, pk):
        option = self.get_object(pk)
        if not option:
            return Response({'error': 'Shawarma option not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = ShawarmaOptionSerializer(option, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        option = self.get_object(pk)
        if not option:
            return Response({'error': 'Shawarma option not found'},
                            status=status.HTTP_404_NOT_FOUND)
        option.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RiceTypeListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        rice_types = RiceType.objects.all()
        serializer = RiceTypeSerializer(rice_types, many=True)
        return Response(serializer.data)

    @extend_schema(request=RiceTypeSerializer)
    def post(self, request):
        serializer = RiceTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RiceTypeDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get_object(self, pk):
        try:
            return RiceType.objects.get(pk=pk)
        except RiceType.DoesNotExist:
            return None

    @extend_schema(request=RiceTypeSerializer)
    def patch(self, request, pk):
        rice_type = self.get_object(pk)
        if not rice_type:
            return Response({'error': 'Rice type not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = RiceTypeSerializer(rice_type, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        rice_type = self.get_object(pk)
        if not rice_type:
            return Response({'error': 'Rice type not found'},
                            status=status.HTTP_404_NOT_FOUND)
        rice_type.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class RiceExtraListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        extras = RiceExtra.objects.filter(is_available=True)
        serializer = RiceExtraSerializer(extras, many=True)
        return Response(serializer.data)

    @extend_schema(request=RiceExtraSerializer)
    def post(self, request):
        serializer = RiceExtraSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RiceExtraDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get_object(self, pk):
        try:
            return RiceExtra.objects.get(pk=pk)
        except RiceExtra.DoesNotExist:
            return None

    @extend_schema(request=RiceExtraSerializer)
    def patch(self, request, pk):
        extra = self.get_object(pk)
        if not extra:
            return Response({'error': 'Extra not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = RiceExtraSerializer(extra, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        extra = self.get_object(pk)
        if not extra:
            return Response({'error': 'Extra not found'},
                            status=status.HTTP_404_NOT_FOUND)
        extra.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class ShawarmaExtraListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        extras = ShawarmaExtra.objects.filter(is_available=True)
        serializer = ShawarmaExtraSerializer(extras, many=True)
        return Response(serializer.data)

    @extend_schema(request=ShawarmaExtraSerializer)
    def post(self, request):
        serializer = ShawarmaExtraSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ShawarmaExtraDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get_object(self, pk):
        try:
            return ShawarmaExtra.objects.get(pk=pk)
        except ShawarmaExtra.DoesNotExist:
            return None

    @extend_schema(request=ShawarmaExtraSerializer)
    def patch(self, request, pk):
        extra = self.get_object(pk)
        if not extra:
            return Response({'error': 'Extra not found'},
                            status=status.HTTP_404_NOT_FOUND)
        serializer = ShawarmaExtraSerializer(extra, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def delete(self, request, pk):
        extra = self.get_object(pk)
        if not extra:
            return Response({'error': 'Extra not found'},
                            status=status.HTTP_404_NOT_FOUND)
        extra.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DrinkListView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def get(self, request):
        drinks = Drink.objects.filter(is_available=True)
        serializer = DrinkSerializer(drinks, many=True)
        return Response(serializer.data)

    @extend_schema(request=DrinkSerializer)
    def post(self, request):
        serializer = DrinkSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DrinkDetailView(APIView):
    permission_classes = [IsAdminOrReadOnly]

    def patch(self, request, pk):
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
        try:
            drink = Drink.objects.get(pk=pk)
        except Drink.DoesNotExist:
            return Response({'error': 'Drink not found'},
                            status=status.HTTP_404_NOT_FOUND)
        drink.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)