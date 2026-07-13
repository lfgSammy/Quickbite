from django.contrib import admin
from .models import (Cart, CartItem, CartItemRiceExtra,
                     CartItemShawarmaExtra, CartItemDrink,
                     Order, OrderItem, OrderItemRiceExtra,
                     OrderItemShawarmaExtra, OrderItemDrink)

admin.site.register(Cart)
admin.site.register(CartItem)
admin.site.register(CartItemRiceExtra)
admin.site.register(CartItemShawarmaExtra)
admin.site.register(CartItemDrink)
admin.site.register(Order)
admin.site.register(OrderItem)
admin.site.register(OrderItemRiceExtra)
admin.site.register(OrderItemShawarmaExtra)
admin.site.register(OrderItemDrink)