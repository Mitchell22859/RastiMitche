"""
Reports - Models.

Report generation and caching for company dashboards.
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class Report(CompanyOwnedModel):
    """
    Generated report for a company.
    Stores report metadata and cached results.
    """

    class ReportType(models.TextChoices):
        ORDERS_SUMMARY = "orders_summary", "Orders Summary"
        REVENUE = "revenue", "Revenue Report"
        TECHNICIAN_PERFORMANCE = "technician_performance", "Technician Performance"
        CUSTOMER_ACTIVITY = "customer_activity", "Customer Activity"

    report_type = models.CharField(max_length=30, choices=ReportType.choices)
    title = models.CharField(max_length=200)
    parameters = models.JSONField(default=dict, blank=True)
    result_data = models.JSONField(default=dict, blank=True)
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at"]

    def __str__(self) -> str:
        return f"{self.title} ({self.report_type})"

# =============================================================================
# DISCOUNT CAMPAIGNS
# =============================================================================

class DiscountCampaign(CompanyOwnedModel):
    """Targeted discount SMS campaign history."""

    class Source(models.TextChoices):
        SEGMENT = "segment", "گزارش هدفمند"
        SINGLE_CUSTOMER = "single_customer", "مشتری خاص"
        MANUAL = "manual", "دستی"

    class Status(models.TextChoices):
        DRAFT = "draft", "پیش‌نویس"
        QUEUED = "queued", "در صف ارسال"
        SENT = "sent", "ارسال شده"
        PARTIAL = "partial", "ارسال ناقص"
        CANCELLED = "cancelled", "لغو شده"

    source = models.CharField(max_length=30, choices=Source.choices, default=Source.SEGMENT, db_index=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    title = models.CharField(max_length=200)

    percent = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    max_discount_rial = models.PositiveBigIntegerField(default=300000)
    expires_at = models.DateTimeField(db_index=True)

    custom_code = models.CharField(max_length=50, blank=True, db_index=True)

    message_template = models.TextField(blank=True)
    filter_snapshot = models.JSONField(default=dict, blank=True)

    created_by_id = models.PositiveIntegerField(null=True, blank=True)
    created_by_username = models.CharField(max_length=150, blank=True)

    recipient_total = models.PositiveIntegerField(default=0)
    excluded_total = models.PositiveIntegerField(default=0)
    code_total = models.PositiveIntegerField(default=0)
    sms_queued_total = models.PositiveIntegerField(default=0)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status", "created_at"], name="disc_campaign_company_idx"),
            models.Index(fields=["company", "source"], name="disc_campaign_source_idx"),
            models.Index(fields=["company", "custom_code"], name="disc_campaign_code_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.title} ({self.status})"


class DiscountCode(CompanyOwnedModel):
    """One-time masked discount code assigned to a customer/phone."""

    class Status(models.TextChoices):
        CREATED = "created", "ساخته شده"
        SMS_QUEUED = "sms_queued", "پیامک در صف"
        USED = "used", "استفاده شده"
        EXPIRED = "expired", "منقضی شده"
        CANCELLED = "cancelled", "لغو شده"

    campaign = models.ForeignKey(
        DiscountCampaign,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="discount_codes",
    )

    customer_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    customer_name_snapshot = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, db_index=True)

    code_hash = models.CharField(max_length=128, db_index=True)
    code_masked = models.CharField(max_length=16)

    percent = models.DecimalField(max_digits=5, decimal_places=2, default=20)
    max_discount_rial = models.PositiveBigIntegerField(default=300000)
    expires_at = models.DateTimeField(db_index=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.CREATED, db_index=True)

    sms_outbox_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    used_invoice_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    used_discount_amount_rial = models.PositiveBigIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        constraints = [
            models.UniqueConstraint(fields=["company", "code_hash"], name="unique_discount_code_hash_per_company"),
        ]
        indexes = [
            models.Index(fields=["company", "phone_number", "status"], name="disc_code_phone_status_idx"),
            models.Index(fields=["company", "expires_at"], name="disc_code_expires_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.code_masked} [{self.status}]"


class DiscountCampaignRecipient(CompanyOwnedModel):
    """Snapshot of every candidate in a campaign, including excluded customers."""

    class Status(models.TextChoices):
        SELECTED = "selected", "انتخاب شده"
        EXCLUDED = "excluded", "حذف شده"
        CODE_CREATED = "code_created", "کد ساخته شد"
        SMS_QUEUED = "sms_queued", "پیامک در صف"
        FAILED = "failed", "ناموفق"

    campaign = models.ForeignKey(
        DiscountCampaign,
        on_delete=models.CASCADE,
        related_name="recipients",
    )

    customer_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    customer_name_snapshot = models.CharField(max_length=200, blank=True)
    phone_number = models.CharField(max_length=20, blank=True, db_index=True)
    email_snapshot = models.EmailField(blank=True)
    last_address_snapshot = models.TextField(blank=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.SELECTED, db_index=True)

    discount_code = models.ForeignKey(
        DiscountCode,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_recipients",
    )
    sms_outbox_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    excluded_by_id = models.PositiveIntegerField(null=True, blank=True)
    excluded_by_username = models.CharField(max_length=150, blank=True)
    excluded_at = models.DateTimeField(null=True, blank=True)
    exclusion_reason = models.CharField(max_length=250, blank=True)

    class Meta:
        ordering = ["id"]
        indexes = [
            models.Index(fields=["company", "campaign", "status"], name="disc_rec_campaign_status_idx"),
            models.Index(fields=["company", "phone_number"], name="disc_rec_phone_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.customer_name_snapshot or self.phone_number} ({self.status})"


class DiscountCampaignAllowedPhone(CompanyOwnedModel):
    """
    Phone whitelist for custom-code campaigns.
    When a campaign has a custom_code, only phones in this list can use it.
    """

    campaign = models.ForeignKey(
        DiscountCampaign,
        on_delete=models.CASCADE,
        related_name="allowed_phones",
    )
    phone = models.CharField(max_length=20)
    normalized_phone = models.CharField(max_length=20, db_index=True)
    customer_id = models.PositiveIntegerField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField(null=True, blank=True)
    used_invoice_id = models.PositiveIntegerField(null=True, blank=True)
    used_discount_amount_rial = models.PositiveBigIntegerField(default=0)

    class Meta:
        ordering = ["id"]
        constraints = [
            models.UniqueConstraint(
                fields=["campaign", "normalized_phone"],
                name="unique_allowed_phone_per_campaign",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "campaign", "normalized_phone"], name="disc_allowed_phone_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.phone} → campaign {self.campaign_id}"
