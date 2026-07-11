from django.db import models
from cloudinary.models import CloudinaryField
    
class MenuItem(models.Model):
    ITEM_TYPE=[
        ('rice','Rice'),
        ('shawarma','Shawarma')
    ]
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    image = CloudinaryField('menu_item', blank=True, null=True)
    item_type = models.CharField(max_length=15, choices=ITEM_TYPE)
    is_available = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name
    
class RiceType(models.Model):
    name = models.CharField(max_length=20)

    def __str__(self):
        return self.name
    
class MenuItemSize(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='sizes')
    name = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    
    def __str__(self):
        return f"{self.menu_item} - {self.name} (₦{self.price})"
    
class ShawarmaOption(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE,
                                  related_name='shawarma_options')
    name = models.CharField(max_length=20)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - ₦{self.price}"
    
class ShawarmaExtra(models.Model):
    name = models.CharField(max_length=50)
    price = models.DecimalField(max_digits=10, decimal_places=2)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f'{self.name} - ₦{self.price}'
    
class Drink(models.Model):
    name = models.CharField(max_length=20)
    price = models.DecimalField(max_length=10, decimal_places=2)
    image = CloudinaryField('drink',blank=True, null=True)
    is_available = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.name} - ₦{self.price}"


