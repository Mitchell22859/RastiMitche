from django.contrib import admin
from django.utils.html import format_html

from .models import (
    Company,
    CompanyFinancialPolicy,
    CompanyGalleryImage,
    CompanyPage,
    CompanyService,
    CompanySettings,
    ServiceRequest,
)


@admin.register(Company)
class CompanyAdmin(admin.ModelAdmin):
    list_display = ["name", "code", "is_active", "email", "created_at"]
    list_filter = ["is_active"]
    search_fields = ["name", "code", "email"]
    prepopulated_fields = {"slug": ("name",)}


@admin.register(CompanyPage)
class CompanyPageAdmin(admin.ModelAdmin):
    list_display = ["company", "is_published", "is_request_form_enabled", "updated_at"]
    list_filter = ["is_published", "is_request_form_enabled"]


@admin.register(CompanyService)
class CompanyServiceAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "base_price", "is_active"]
    list_filter = ["is_active", "company"]


@admin.register(CompanyGalleryImage)
class CompanyGalleryImageAdmin(admin.ModelAdmin):
    list_display = ["caption", "company", "sort_order", "is_active"]
    list_filter = ["is_active", "company"]


@admin.register(ServiceRequest)
class ServiceRequestAdmin(admin.ModelAdmin):
    list_display = ["customer_name", "customer_phone", "company", "service", "created_at"]
    list_filter = ["company"]
    search_fields = ["customer_name", "customer_phone"]



@admin.register(CompanyFinancialPolicy)
class CompanyFinancialPolicyAdmin(admin.ModelAdmin):
    """
    WARNING: These financial policy settings affect how discounts are split
    between the company and technician at settlement. Changes take effect on
    future settlements only — historical records are not retroactively changed.
    Contact your system administrator before modifying any policy.
    """
    list_display = ["company", "campaign_discount_policy", "extra_discount_policy", "updated_at"]
    readonly_fields = ["company", "campaign_discount_policy", "extra_discount_policy", "created_at", "updated_at"]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(CompanySettings)
class CompanySettingsAdmin(admin.ModelAdmin):
    list_display = [
        "company",
        "priority2_delay_minutes",
        "priority3_delay_minutes",
        "max_active_orders_per_technician",
        "auto_recycle_cancel_request",
    ]
    list_filter = ["auto_recycle_cancel_request", "show_future_orders_to_technicians"]
