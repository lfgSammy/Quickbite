from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('users/<int:user_id>/assign-role/', views.AssignRoleView.as_view(), name='assign-role'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/profile/', views.ProfileView.as_view(), name='profile'),
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('restaurant/status/', views.RestaurantStatusView.as_view(), name='restaurant-status'),
]