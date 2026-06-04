"""
SMS Master Templates and Change Requests.

Phase 19A: Platform-controlled SMS master templates.

Architecture:
- SMSMasterTemplate: Platform-owned master template for each event key.
  NOT company-scoped. Owned and managed by platform owner only.
- SMSTemplateChangeRequest: Company admin requests to change template wording.
  Company-scoped. Reviewed by platform owner.

Resolution (to be implemented in Phase 19B+):
1. Company-specific approved override (existing SMSTemplate row with approved text)
2. Fallback to SMSMasterTemplate
"""
from django.conf import settings
from django.db import models


class SMSMasterTemplate(models.Model):
    """
    Platform-owned master SMS template.

    NOT company-scoped — this is a global/platform-level template.
    Platform owner creates and manages these.
    Companies see the effective template text but cannot edit directly.
    """

    class Scope(models.TextChoices):
        COMPANY = "company", "شرکت (پرداخت شرکت)"
        PLATFORM = "platform", "پلتفرم (پرداخت مالک)"

    class RecipientType(models.TextChoices):
        CUSTOMER = "customer", "مشتری"
        TECHNICIAN = "technician", "نیروی خدماتی"
        ADMIN = "admin", "مدیر شرکت"
        PLATFORM_ADMIN = "platform_admin", "مدیر پلتفرم"

    key = models.CharField(
        max_length=80,
        unique=True,
        db_index=True,
        help_text="Event key matching NotificationSetting / PlatformSMSMessageTypeSetting keys.",
    )
    scope = models.CharField(
        max_length=10,
        choices=Scope.choices,
        default=Scope.COMPANY,
    )
    recipient_type = models.CharField(
        max_length=20,
        choices=RecipientType.choices,
        default=RecipientType.CUSTOMER,
    )
    title = models.CharField(max_length=200)
    template_text = models.TextField(
        help_text="Django template syntax. Variables: {{ company_name }}, {{ customer_name }}, etc.",
    )
    allowed_variables = models.TextField(
        blank=True,
        help_text="Comma-separated list of supported variables for this template.",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scope", "key"]
        verbose_name = "SMS Master Template"
        verbose_name_plural = "SMS Master Templates"

    def __str__(self):
        return f"[{self.get_scope_display()}] {self.title} ({self.key})"


class SMSTemplateChangeRequest(models.Model):
    """
    Company admin request to change SMS template wording/tone.

    Company-scoped: each request belongs to a specific company.
    Platform owner reviews and approves/rejects.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "در انتظار بررسی"
        APPROVED = "approved", "تایید شده"
        REJECTED = "rejected", "رد شده"

    class Tone(models.TextChoices):
        FORMAL = "formal", "رسمی"
        FRIENDLY = "friendly", "دوستانه"
        SHORT = "short", "کوتاه و عملیاتی"
        DETAILED = "detailed", "مفصل و توضیحی"
        CUSTOM = "custom", "سفارشی"

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="sms_template_change_requests",
    )
    event_key = models.CharField(max_length=80)
    current_template_text = models.TextField(
        blank=True,
        help_text="Snapshot of the template text at request time.",
    )
    requested_template_text = models.TextField(
        help_text="The new text requested by company admin.",
    )
    requested_tone = models.CharField(
        max_length=10,
        choices=Tone.choices,
        default=Tone.CUSTOM,
    )
    note = models.TextField(
        blank=True,
        help_text="Company admin's reason/note for the change.",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_sms_template_requests",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    admin_response = models.TextField(
        blank=True,
        help_text="Platform owner's response/note on approval or rejection.",
    )
    approved_template_text = models.TextField(
        blank=True,
        help_text="Final text approved/corrected by platform owner. May differ from requested_template_text.",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="submitted_sms_template_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "SMS Template Change Request"
        verbose_name_plural = "SMS Template Change Requests"

    def __str__(self):
        return f"{self.company.code} / {self.event_key} ({self.get_status_display()})"
