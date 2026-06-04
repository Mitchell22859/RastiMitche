"""
SMS models.

Clean tenant-scoped SMS outbox.

Rules:
- Every provider, template and outbox row belongs to exactly one company.
- New messages are queued only. Credit is checked and debited only when the worker sends.
- No legacy SMS state is supported because the product has no old SMS data.
"""
from django.db import models
from django.utils import timezone

from apps.common.models import CompanyOwnedModel


class SMSProvider(CompanyOwnedModel):
    """SMS provider configuration for a tenant company."""

    class ProviderType(models.TextChoices):
        KAVENEGAR = "kavenegar", "Kavenegar"
        GHASEDAK = "ghasedak", "Ghasedak"
        MELIPAYAMAK = "melipayamak", "MeliPayamak"
        FAKE = "fake", "Fake (Testing)"

    name = models.CharField(max_length=100)
    provider_type = models.CharField(max_length=20, choices=ProviderType.choices)
    api_key = models.CharField(max_length=300)
    sender_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["company_id", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.provider_type})"


class SMSTemplate(CompanyOwnedModel):
    """Company-scoped SMS template. Each company owns and edits its own text."""

    class TemplateKey(models.TextChoices):
        COMPANY_REGISTERED = 'company_registered', 'ثبت\u200cنام شرکت جدید'
        COMPANY_ACTIVATED = 'company_activated', 'فعال\u200cسازی شرکت'
        COMPANY_REJECTED = 'company_rejected', 'رد شرکت'
        COMPANY_ADMIN_PASSWORD_RESET = 'company_admin_password_reset', 'بازنشانی رمز عبور مدیر'
        OPERATOR_CREATED = 'operator_created', 'ایجاد اپراتور'
        TECHNICIAN_CREATED = 'technician_created', 'ایجاد نیروی خدماتی'
        TECHNICIAN_STATUS_CHANGED = 'technician_status_changed', 'تغییر وضعیت نیروی خدماتی'
        TECHNICIAN_WAGE_PERCENT_CHANGED = 'technician_wage_percent_changed', 'تغییر درصد اجرت نیرو'
        SERVICE_CATEGORY_CREATED = 'service_category_created', 'ایجاد رسته خدمات'
        SERVICE_ITEM_CREATED = 'service_item_created', 'ایجاد آیتم خدمات'
        ORDER_CREATED_ADMIN = 'order_created_admin', 'سفارش جدید - مدیر شرکت'
        ORDER_CREATED_CUSTOMER = 'order_created_customer', 'سفارش جدید - مشتری'
        ORDER_AVAILABLE_TECHNICIAN = 'order_available_technician', 'سفارش جدید برای نیروها'
        ORDER_ASSIGNED_TECHNICIAN = 'order_assigned_technician', 'تخصیص سفارش به نیرو'
        ORDER_ACCEPTED_CUSTOMER = 'order_accepted_customer', 'پذیرش سفارش - مشتری'
        ORDER_STARTED = 'order_started', 'شروع سفارش'
        ORDER_COMPLETED_CUSTOMER = 'order_completed_customer', 'اتمام سفارش - مشتری'
        ORDER_CANCEL_REQUESTED_CUSTOMER = 'order_cancel_requested_customer', 'درخواست لغو توسط مشتری'
        ORDER_CANCEL_REQUESTED_ADMIN = 'order_cancel_requested_admin', 'درخواست لغو سفارش - مدیر'
        ORDER_CANCEL_APPROVED_TECHNICIAN = 'order_cancel_approved_technician', 'تأیید لغو - نیرو'
        ORDER_CANCEL_REJECTED_TECHNICIAN = 'order_cancel_rejected_technician', 'رد لغو - نیرو'
        ORDER_CANCELLED = 'order_cancelled', 'لغو سفارش'
        ORDER_RESCHEDULED = 'order_rescheduled', 'تغییر زمان سفارش'
        INVOICE_ISSUED_CUSTOMER = 'invoice_issued_customer', 'صدور فاکتور - مشتری'
        INVOICE_SENT_CUSTOMER = 'invoice_sent_customer', 'ارسال فاکتور - مشتری'
        INVOICE_PAID_CUSTOMER = 'invoice_paid_customer', 'پرداخت فاکتور - مشتری'
        PAYMENT_SUCCESS_CUSTOMER = 'payment_success_customer', 'پرداخت موفق - مشتری'
        PAYMENT_FAILED_CUSTOMER = 'payment_failed_customer', 'پرداخت ناموفق - مشتری'
        WALLET_CHARGED = 'wallet_charged', 'شارژ کیف پول پیامک'
        SMS_CREDIT_LOW_ADMIN = 'sms_credit_low_admin', 'کم بودن اعتبار پیامک'
        SMS_CREDIT_EMPTY_ADMIN = 'sms_credit_empty_admin', 'اتمام اعتبار پیامک'
        SMS_TEMPLATE_CHANGE_REQUESTED = 'sms_template_change_requested', 'درخواست تغییر قالب پیامک'
        SMS_TEMPLATE_CHANGE_APPROVED = 'sms_template_change_approved', 'تأیید تغییر قالب پیامک'
        SMS_TEMPLATE_CHANGE_REJECTED = 'sms_template_change_rejected', 'رد تغییر قالب پیامک'
        SMS_OUTBOX_FAILED = 'sms_outbox_failed', 'خطا در ارسال پیامک'
        SUBSCRIPTION_EXPIRING_ADMIN = 'subscription_expiring_admin', 'نزدیک شدن پایان اشتراک'
        SUBSCRIPTION_EXPIRED_ADMIN = 'subscription_expired_admin', 'پایان اشتراک'
        PLATFORM_PAYMENT_SUCCESS_ADMIN = 'platform_payment_success_admin', 'پرداخت موفق پلتفرمی'
        SURVEY_REQUEST_CUSTOMER = 'survey_request_customer', 'نظرسنجی - مشتری'


    key = models.CharField(max_length=80, choices=TemplateKey.choices)
    title = models.CharField(max_length=200)
    template_text = models.TextField(
        help_text="Django template syntax. Example: {{ order_id }}, {{ customer_name }}",
    )
    is_active = models.BooleanField(default=True)
    send_start_time = models.TimeField(null=True, blank=True)
    send_end_time = models.TimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["company", "key"],
                name="unique_sms_template_per_company",
            ),
        ]
        ordering = ["key"]

    def __str__(self) -> str:
        return f"{self.title} ({self.get_key_display()})"


class SMSOutbox(CompanyOwnedModel):
    """
    Tenant-scoped SMS outbox record.

    Status lifecycle:
        queued -> sending -> sent -> delivered
        queued/sending -> failed
        queued/failed -> cancelled
    """

    class Status(models.TextChoices):
        QUEUED = "queued", "در صف ارسال"
        SENDING = "sending", "در حال ارسال"
        SENT = "sent", "ارسال شده"
        DELIVERED = "delivered", "ارسال موفق"
        FAILED = "failed", "ارسال ناموفق"
        CANCELLED = "cancelled", "لغو شده"

    provider = models.ForeignKey(
        SMSProvider,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="messages",
    )
    template = models.ForeignKey(
        SMSTemplate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbox_messages",
    )
    template_key = models.CharField(
        max_length=80,
        choices=SMSTemplate.TemplateKey.choices,
        blank=True,
    )

    phone_number = models.CharField(max_length=15)
    message = models.TextField()

    # Pricing snapshot captured when the SMSOutbox row is created.
    # These values must not change later if the platform owner changes SMS pricing.
    message_length_snapshot = models.PositiveIntegerField(default=0)
    sms_parts_snapshot = models.PositiveIntegerField(default=0)
    sms_cost_rial_snapshot = models.BigIntegerField(default=0)
    pricing_characters_per_sms_snapshot = models.PositiveIntegerField(default=0)
    pricing_price_per_sms_rial_snapshot = models.PositiveIntegerField(default=0)
    pricing_snapshot_at = models.DateTimeField(null=True, blank=True)

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )

    provider_message_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    attempt_count = models.PositiveIntegerField(default=0)

    queued_at = models.DateTimeField(default=timezone.now)
    sending_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    send_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Scheduled send time. Empty means send as soon as possible.",
    )

    order_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)
    invoice_id = models.PositiveIntegerField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status", "send_at"], name="sms_outbox_company_due_idx"),
            models.Index(fields=["company", "phone_number", "template_key"], name="sms_outbox_company_phone_idx"),
        ]
        verbose_name = "SMS Outbox"
        verbose_name_plural = "SMS Outbox"

    def __str__(self) -> str:
        return f"SMS to {self.phone_number} ({self.status})"



# Phase 19A: Platform-controlled master templates and change requests
from .models_master import SMSMasterTemplate, SMSTemplateChangeRequest  # noqa: F401
