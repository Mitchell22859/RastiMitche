from django.contrib import admin

from .models import BillingRecord


@admin.register(BillingRecord)
class BillingRecordAdmin(admin.ModelAdmin):
    list_display = ["company", "amount", "is_paid", "paid_at", "created_at"]
    list_filter = ["is_paid", "company"]
