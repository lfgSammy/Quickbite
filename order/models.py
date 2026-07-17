from django.db import models
import uuid
from users.models import User
from menu.models import (MenuItem, MenuItemSize, RiceType, RiceExtra,
                         ShawarmaExtra, ShawarmaOption, Drink)


class Cart(models.Model):
    customer = models.OneToOneField(
        User, on_delete=models.CASCADE, related_name='cart')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.customer.username}'s Cart"

    def get_total(self):
        return sum(item.get_total() for item in self.items.all())


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE)
    size = models.ForeignKey(
        MenuItemSize, on_delete=models.SET_NULL, null=True, blank=True)
    rice_type = models.ForeignKey(
        RiceType, on_delete=models.SET_NULL, null=True, blank=True)
    shawarma_option = models.ForeignKey(
        ShawarmaOption, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.menu_item.name} x {self.quantity}"

    def get_base_price(self):
        if self.size:
            return self.size.price
        if self.shawarma_option:
            return self.shawarma_option.price
        return 0

    def get_extras_total(self):
        rice_extras = sum(
            e.extra.price * e.quantity
            for e in self.rice_extras.all()
        )
        shawarma_extras = sum(
            e.extra.price
            for e in self.shawarma_extras.filter(is_added=True)
        )
        return rice_extras + shawarma_extras

    def get_drinks_total(self):
        return sum(
            d.drink.price * d.quantity
            for d in self.drinks.all()
        )

    def get_total(self):
        return (
            (self.get_base_price() * self.quantity) +
            self.get_extras_total() +
            self.get_drinks_total()
        )


class CartItemRiceExtra(models.Model):
    cart_item = models.ForeignKey(
        CartItem, on_delete=models.CASCADE, related_name='rice_extras')
    extra = models.ForeignKey(RiceExtra, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart_item', 'extra')

    def __str__(self):
        return f"{self.extra.name} x {self.quantity}"


class CartItemShawarmaExtra(models.Model):
    cart_item = models.ForeignKey(
        CartItem, on_delete=models.CASCADE, related_name='shawarma_extras')
    extra = models.ForeignKey(ShawarmaExtra, on_delete=models.CASCADE)
    is_added = models.BooleanField(default=False)

    class Meta:
        unique_together = ('cart_item', 'extra')

    def __str__(self):
        return f"{self.extra.name} - {'Added' if self.is_added else 'Not added'}"


class CartItemDrink(models.Model):
    cart_item = models.ForeignKey(
        CartItem, on_delete=models.CASCADE, related_name='drinks')
    drink = models.ForeignKey(Drink, on_delete=models.CASCADE)
    quantity = models.PositiveIntegerField(default=1)

    class Meta:
        unique_together = ('cart_item', 'drink')

    def __str__(self):
        return f"{self.drink.name} x {self.quantity}"


class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('preparing', 'Preparing'),
        ('ready', 'Ready'),
        ('collected', 'Collected'),
        ('cancelled', 'Cancelled'),
    ]
    customer = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name='orders')
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default='pending')
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    pickup_time = models.DateTimeField()
    qr_code = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Order #{self.id} - {self.status}"


class OrderItem(models.Model):
    order = models.ForeignKey(
        Order, on_delete=models.CASCADE, related_name='items')
    menu_item = models.ForeignKey(MenuItem, on_delete=models.PROTECT)
    size_name = models.CharField(max_length=20, blank=True)
    size_price = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    rice_type_name = models.CharField(max_length=20, blank=True)
    shawarma_option_name = models.CharField(max_length=50, blank=True)
    shawarma_option_price = models.DecimalField(
        max_digits=10, decimal_places=2, default=0)
    quantity = models.PositiveIntegerField(default=1)
    item_total = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    def __str__(self):
        return f"{self.menu_item.name} x {self.quantity}"


class OrderItemRiceExtra(models.Model):
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name='rice_extras')
    extra_name = models.CharField(max_length=50)
    extra_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.extra_name} x {self.quantity}"


class OrderItemShawarmaExtra(models.Model):
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name='shawarma_extras')
    extra_name = models.CharField(max_length=50)
    extra_price = models.DecimalField(max_digits=10, decimal_places=2)
    is_added = models.BooleanField(default=True)

    def __str__(self):
        return self.extra_name


class OrderItemDrink(models.Model):
    order_item = models.ForeignKey(
        OrderItem, on_delete=models.CASCADE, related_name='drinks')
    drink_name = models.CharField(max_length=100)
    drink_price = models.DecimalField(max_digits=10, decimal_places=2)
    quantity = models.PositiveIntegerField(default=1)

    def __str__(self):
        return f"{self.drink_name} x {self.quantity}"