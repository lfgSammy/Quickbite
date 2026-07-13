from django.contrib import admin
from .models import (MenuItem, MenuItemSize, RiceType,
                     ShawarmaOption, RiceExtra, ShawarmaExtra, Drink)

admin.site.register(MenuItem)
admin.site.register(MenuItemSize)
admin.site.register(RiceType)
admin.site.register(ShawarmaOption)
admin.site.register(RiceExtra)
admin.site.register(ShawarmaExtra)
admin.site.register(Drink)