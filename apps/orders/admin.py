from django.contrib import admin

from .models import Order, OrderItemDefinition, OrderItemValue, OrderStatusLog


class OrderStatusLogInline(admin.TabularInline):
    model = OrderStatusLog
    extra = 0
    readonly_fields = ["old_status", "new_status", "changed_by", "created_at"]


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ["id", "title", "company", "status", "priority", "technician", "created_at"]
    list_filter = ["status", "priority", "company"]
    search_fields = ["title", "description"]
    inlines = [OrderStatusLogInline]


@admin.register(OrderStatusLog)
class OrderStatusLogAdmin(admin.ModelAdmin):
    list_display = ["order", "old_status", "new_status", "changed_by", "created_at"]
    list_filter = ["new_status", "company"]
    readonly_fields = ["order", "old_status", "new_status", "changed_by", "created_at"]



@admin.register(OrderItemDefinition)
class OrderItemDefinitionAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "category", "kind", "is_active", "sort_order"]
    list_filter = ["kind", "is_active", "company"]
    search_fields = ["title"]


@admin.register(OrderItemValue)
class OrderItemValueAdmin(admin.ModelAdmin):
    list_display = ["order", "item", "value_number", "value_text", "value_bool"]
    list_filter = ["item__company"]
    search_fields = ["item__title"]
