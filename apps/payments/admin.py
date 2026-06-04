from django.contrib import admin

from .models import Payment, PaymentAttempt, PaymentGateway


class PaymentAttemptInline(admin.TabularInline):
    model = PaymentAttempt
    extra = 0
    readonly_fields = ["status", "gateway_reference", "gateway_response", "created_at"]


@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "gateway_type", "is_active", "is_default"]
    list_filter = ["gateway_type", "is_active", "company"]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "invoice", "amount", "status", "tracking_code", "paid_at"]
    list_filter = ["status", "company"]
    inlines = [PaymentAttemptInline]


@admin.register(PaymentAttempt)
class PaymentAttemptAdmin(admin.ModelAdmin):
    list_display = ["id", "payment", "status", "gateway_reference", "created_at"]
    list_filter = ["status"]
