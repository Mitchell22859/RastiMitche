from django.contrib import admin

from .models import TechnicianLedgerEntry


@admin.register(TechnicianLedgerEntry)
class TechnicianLedgerEntryAdmin(admin.ModelAdmin):
    list_display = [
        "id", "company", "technician", "entry_type", "source",
        "amount_rial", "balance_after", "idempotency_key", "created_at",
    ]
    list_filter = ["entry_type", "source", "company"]
    search_fields = ["idempotency_key", "description"]
    readonly_fields = [
        "company", "technician", "invoice", "payment", "order",
        "entry_type", "source", "amount_rial", "balance_after",
        "idempotency_key", "created_by", "metadata", "created_at", "updated_at",
    ]
