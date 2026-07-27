from django.contrib import admin
from .models import User, Notification, OperatingHours

admin.site.register(User)
admin.site.register(OperatingHours)
admin.site.register(Notification)