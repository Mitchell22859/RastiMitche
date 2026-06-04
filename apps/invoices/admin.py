from django.contrib import admin

from .models import Invoice, InvoiceItem


class InvoiceItemInline(admin.TabularInline):
    model = InvoiceItem
    extra = 0


@admin.register(Invoice)
class InvoiceAdmin(admin.ModelAdmin):
    list_display = ["invoice_number", "company", "status", "total_amount", "customer", "created_at"]
    list_filter = ["status", "company"]
    search_fields = ["invoice_number"]
    inlines = [InvoiceItemInline]
