"""
Payouts - Models.

Financial ledger for technician wages and settlements.

Convention:
  CREDIT  → company owes technician (positive balance contribution)
  DEBIT   → technician owes company, or has been paid out (negative balance contribution)
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class TechnicianLedgerEntry(CompanyOwnedModel):
    """
    One immutable row in the technician's financial ledger.

    balance_after stores the technician's running balance immediately after
    this entry was applied. Positive = company still owes technician.
    Negative = technician still owes company.

    idempotency_key is globally unique. Callers must set a deterministic key
    (e.g. "invoice:42:technician_credit") so that replayed callbacks or
    management commands never create duplicate rows.
    """

    class EntryType(models.TextChoices):
        CREDIT = "credit", "بستانکار"
        DEBIT = "debit", "بدهکار"

    class Source(models.TextChoices):
        ONLINE_GATEWAY = "online_gateway", "پرداخت آنلاین"
        CASH_FROM_CUSTOMER = "cash_from_customer", "نقدی از مشتری (تکنسین)"
        MANUAL_PAYMENT = "manual_payment", "پرداخت دستی"
        MANUAL_SETTLEMENT = "manual_settlement", "تسویه دستی"
        DIRECT_GATEWAY_SETTLEMENT = "direct_gateway_settlement", "تسویه مستقیم درگاه"
        ADJUSTMENT = "adjustment", "تعدیل"
        REFUND = "refund", "بازگشت وجه"

    technician = models.ForeignKey(
        "accounts.Technician",
        on_delete=models.PROTECT,
        related_name="ledger_entries",
        db_index=True,
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ledger_entries",
    )

    entry_type = models.CharField(max_length=10, choices=EntryType.choices, db_index=True)
    source = models.CharField(max_length=40, choices=Source.choices, db_index=True)

    amount_rial = models.PositiveBigIntegerField()
    balance_after = models.BigIntegerField(
        help_text="Running balance after this entry. Positive = company owes tech."
    )

    description = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=200, unique=True, db_index=True)

    created_by = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_ledger_entries",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["company", "technician", "created_at"],
                name="ledger_company_tech_date_idx",
            ),
            models.Index(
                fields=["company", "technician", "entry_type"],
                name="ledger_company_tech_type_idx",
            ),
        ]

    def __str__(self) -> str:
        sign = "+" if self.entry_type == self.EntryType.CREDIT else "-"
        return f"{sign}{self.amount_rial:,} [{self.source}] key={self.idempotency_key}"
