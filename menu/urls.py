from django.urls import path
from . import views

urlpatterns = [
    path('menu/', views.MenuItemListView.as_view(), name='menu-list'),
    path('menu/<int:pk>/', views.MenuItemDetailView.as_view(), name='menu-detail'),
]