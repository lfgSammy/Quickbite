from django.db import models
from django.contrib.auth.models import AbstractUser
import random
from datetime import timezone, timedelta

class User(AbstractUser):
    ROLE_CHOICES = [
        ('customer', 'Customer'),
        ('kitchen','Kitchen'),
        ('admin', 'Admin')
    ]
    email = models.EmailField(unique=True)
    role = models.CharField(max_length=10,choices=ROLE_CHOICES, default='customer')
    phone_number = models.CharField(max_length=11, blank=True, null=True, unique=True)

    def __str__(self):
        return f"{self.username}: {self.role.upper()}"
    
    @property
    def is_kitchen(self):
        return self.role == 'kitchen'
    
    @property
    def is_admin(self):
        return self.role == 'admin' or self.is_superuser
    
    @property
    def is_customer(self):
        return self.role == 'customer' and not self.is_superuser

class PasswordResetOTP(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_reset')
    code = models.CharField(max_length=6)
    is_used = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateField()

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at= timezone.now() + timedelta(minutes=10)
        super().save(*args, **kwargs)

    def is_valid(self):
        return not self.is_used and timezone.now() < self.expires_at

    @staticmethod
    def generate_codes():
        return str(random.randint(100000, 999999))

    def __str__(self):
        return f"Password reset OTP for{self.user.username}"
    
    

class OperatingHours(models.Model):
    DAY_CHOICES = [
        (0, 'Monday'), (1, 'Tuesday'), (2, 'Wednesday'),
        (3, 'Thursday'), (4, 'Friday'), (5, 'Saturday'), (6, 'Sunday'),
    ]
    day = models.IntegerField(choices=DAY_CHOICES, unique=True)
    open_time = models.TimeField()
    close_time = models.TimeField()
    is_open = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.get_day_display()} - {self.open_time} to {self.close_time}"

    
class Notification(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    message = models.TextField()
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Notification for {self.user.username}"