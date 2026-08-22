from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

urlpatterns = [
    path('auth/register/', views.RegisterView.as_view(), name='register'),
    path('auth/login/', views.LoginView.as_view(), name='login'),
    path('auth/forgot-password/', views.ForgotPasswordView.as_view(), name='forgot-password'),
    path('auth/verify-reset-otp/', views.VerifyResetOTPView.as_view(), name='verify-reset-otp'),
    path('auth/reset-password/', views.ResetPasswordView.as_view(), name='reset-password'),
    path('users/', views.UserListView.as_view(), name='user-list'),
    path('users/<int:user_id>/assign-role/', views.AssignRoleView.as_view(), name='assign-role'),
    path('auth/refresh/', TokenRefreshView.as_view(), name='token-refresh'),
    path('auth/google/', views.GoogleOAuthView.as_view(), name='google-oauth'),
    path('auth/profile/', views.ProfileView.as_view(), name='profile'),
    path('notifications/', views.NotificationListView.as_view(), name='notifications'),
    path('restaurant/status/', views.RestaurantStatusView.as_view(), name='restaurant-status'),
    path('restaurant/hours/', views.OperatingHoursView.as_view(), name='operating-hours'),
]