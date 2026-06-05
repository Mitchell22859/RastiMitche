from django.contrib import admin

from .models import TechnicianLedgerEntry, PaymentSplitSnapshot


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


@admin.register(PaymentSplitSnapshot)
class PaymentSplitSnapshotAdmin(admin.ModelAdmin):
    list_display = [
        "id", "company", "payment", "should_split_with_technician", "reason",
        "total_amount", "technician_direct_amount", "technician_ledger_amount",
        "payout_strategy_snapshot", "technician_verified_snapshot", "created_at",
    ]
    list_filter = ["should_split_with_technician", "payout_strategy_snapshot", "company"]
    readonly_fields = [f.name for f in PaymentSplitSnapshot._meta.get_fields() if hasattr(f, "name")]
