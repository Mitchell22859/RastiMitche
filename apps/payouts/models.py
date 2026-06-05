"""
Payouts - Models.

Financial ledger for technician wages and settlements.
Also contains PaymentSplitSnapshot for split-decision audit trail.

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


class PaymentSplitSnapshot(CompanyOwnedModel):
    """
    Immutable audit record of the split decision made at payment initiation/verification.

    Written once per payment. Answers:
    - What was the payout strategy at the time of this payment?
    - Was the technician verified?
    - How much goes directly to the technician vs. stays in company account?

    This snapshot is NOT the ledger (TechnicianLedgerEntry handles balances).
    It is the audit trail for the split routing decision.
    """

    payment = models.OneToOneField(
        "payments.Payment",
        on_delete=models.CASCADE,
        related_name="split_snapshot",
    )
    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="split_snapshots",
    )

    # --- Amounts at decision time ---
    total_amount = models.PositiveBigIntegerField(default=0)
    platform_fee_amount = models.PositiveBigIntegerField(default=0)
    company_deposit_amount = models.PositiveBigIntegerField(default=0)
    technician_direct_amount = models.PositiveBigIntegerField(default=0)
    technician_ledger_amount = models.PositiveBigIntegerField(default=0)

    # --- Snapshot of settings at decision time ---
    payout_strategy_snapshot = models.CharField(max_length=30, blank=True)
    technician_verified_snapshot = models.BooleanField(default=False)
    technician_sub_merchant_id_snapshot = models.CharField(max_length=100, blank=True)
    platform_fee_percent_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=0
    )

    should_split_with_technician = models.BooleanField(default=False)
    reason = models.CharField(max_length=300, blank=True)
    raw_decision = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"SplitSnapshot payment={self.payment_id} split={self.should_split_with_technician}"


class CompanyPlatformFeeEntry(CompanyOwnedModel):
    """
    One immutable row in the company's platform-fee ledger.

    Convention (from platform's perspective):
      DEBIT  → company owes platform more (fee accrued on a cash/manual payment).
      CREDIT → company paid / platform fee was settled.

    balance_after is the running total of what the company owes the platform
    at the moment this entry was written. Positive = company still owes.

    idempotency_key is globally unique.  Callers must supply a deterministic key
    (e.g. "platform_fee:invoice:42") so that retries never double-create.
    """

    class EntryType(models.TextChoices):
        DEBIT = "debit", "بدهکار (شرکت به پلتفرم)"
        CREDIT = "credit", "بستانکار (تسویه)"

    class Source(models.TextChoices):
        CASH_INVOICE = "cash_invoice", "فاکتور نقدی"
        ONLINE_GATEWAY = "online_gateway", "درگاه آنلاین"
        MANUAL_ADJUSTMENT = "manual_adjustment", "تعدیل دستی"
        PLATFORM_FEE_SETTLEMENT = "platform_fee_settlement", "تسویه کارمزد"
        REFUND = "refund", "برگشت"

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_fee_entries",
    )
    payment = models.ForeignKey(
        "payments.Payment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_fee_entries",
    )

    entry_type = models.CharField(max_length=10, choices=EntryType.choices, db_index=True)
    source = models.CharField(max_length=40, choices=Source.choices, db_index=True)

    amount_rial = models.PositiveBigIntegerField()
    balance_after = models.BigIntegerField(
        help_text="Running balance after this entry. Positive = company still owes platform."
    )
    platform_fee_percent_snapshot = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="Platform fee percent at time of recording.",
    )

    description = models.TextField(blank=True)
    idempotency_key = models.CharField(max_length=200, unique=True, db_index=True)

    created_by = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_platform_fee_entries",
    )
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["company", "created_at"],
                name="platform_fee_company_date_idx",
            ),
        ]

    def __str__(self) -> str:
        sign = "+" if self.entry_type == self.EntryType.DEBIT else "-"
        return f"{sign}{self.amount_rial:,} [{self.source}] key={self.idempotency_key}"
