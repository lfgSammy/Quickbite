from django.urls import path
from . import views

urlpatterns = [
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/items/<int:item_id>/', views.CartItemView.as_view(), name='cart-item'),
    path('orders/', views.OrderListView.as_view(), name='order-list'),
    path('orders/<int:order_id>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('orders/verify-qr/', views.VerifyQRView.as_view(), name='verify-qr'),
]