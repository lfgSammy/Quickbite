from django.contrib import admin
from .models import User, Notification, OperatingHours, PasswordResetOTP

admin.site.register(User)
admin.site.register(PasswordResetOTP)
admin.site.register(OperatingHours)
admin.site.register(Notification)