from django.urls import path
from . import views

urlpatterns = [
    path('cart/', views.CartView.as_view(), name='cart'),
    path('cart/items/', views.CartItemView.as_view(), name='cart-item-add'),
    path('cart/items/<int:item_id>/', views.CartItemView.as_view(), name='cart-item-delete'),
    path('orders/', views.OrderListView.as_view(), name='order-list'),
    path('orders/<int:order_id>/', views.OrderDetailView.as_view(), name='order-detail'),
    path('orders/verify-qr/', views.VerifyQRView.as_view(), name='verify-qr'),
    path('admin/dashboard/', views.AdminDashboardView.as_view(), name='admin-dashboard'),
    path('orders/<int:order_id>/cancel/', views.CancelOrderView.as_view(), name='cancel-order'),
    path('orders/<int:order_id>/revert/', views.RevertOrderToCartView.as_view(), name='revert-order'),
    path('cart/items/<int:item_id>/update/', views.UpdateCartItemView.as_view(), name='update-cart-item'),
]