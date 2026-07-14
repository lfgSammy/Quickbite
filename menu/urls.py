from django.urls import path
from . import views

urlpatterns = [
    path('menu/', views.MenuItemListView.as_view(), name='menu-list'),
    path('menu/<int:pk>/', views.MenuItemDetailView.as_view(), name='menu-detail'),
    path('rice-types/', views.RiceTypeListView.as_view(), name='rice-types'),
    path('rice-extras/', views.RiceExtraListView.as_view(), name='rice-extras'),
    path('rice-extras/<int:pk>/', views.RiceExtraDetailView.as_view(), name='rice-extra-detail'),
    path('shawarma-extras/', views.ShawarmaExtraListView.as_view(), name='shawarma-extras'),
    path('shawarma-extras/<int:pk>/', views.ShawarmaExtraDetailView.as_view(), name='shawarma-extra-detail'),
    path('drinks/', views.DrinkListView.as_view(), name='drink-list'),
    path('drinks/<int:pk>/', views.DrinkDetailView.as_view(), name='drink-detail'),
]