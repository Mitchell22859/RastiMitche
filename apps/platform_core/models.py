"""
Platform-level models.

These models are NOT tenant-scoped.
They belong to the platform owner and manage global resources.
"""
from django.conf import settings
from django.db import models


class Plan(models.Model):
    """
    Subscription plan available on the platform.
    Platform-level model — not tenant-scoped.
    """

    name = models.CharField(max_length=100)
    code = models.SlugField(unique=True)
    description = models.TextField(blank=True)
    price_monthly = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    price_yearly = models.DecimalField(max_digits=12, decimal_places=0, default=0)
    max_users = models.PositiveIntegerField(default=5)
    max_technicians = models.PositiveIntegerField(default=10)
    max_orders_per_month = models.PositiveIntegerField(default=100)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["price_monthly"]

    def __str__(self) -> str:
        return self.name


class Subscription(models.Model):
    """
    A company's subscription to a plan.
    Links a tenant (Company) to a Plan with billing dates.
    """

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        TRIAL = "trial", "Trial"
        EXPIRED = "expired", "Expired"
        CANCELLED = "cancelled", "Cancelled"

    company = models.OneToOneField(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="subscription",
    )
    plan = models.ForeignKey(
        Plan,
        on_delete=models.PROTECT,
        related_name="subscriptions",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.TRIAL,
    )
    started_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.company.name} - {self.plan.name} ({self.status})"



class PlatformMessage(models.Model):
    """
    Internal message center for Platform Owner.

    Stores messages that the Platform Owner sends to companies/users
    or receives from the system. Currently internal-only — no real
    SMS/email delivery.

    TODO (Future):
    - Connect to SMS provider for actual delivery
    - Connect to email provider for email delivery
    - Add tenant company inbox for inbound messages
    - Add message templates system
    - Add WhatsApp/Telegram channel support
    """

    class RecipientType(models.TextChoices):
        PLATFORM_OWNER = "PLATFORM_OWNER", "مدیر پلتفرم"
        COMPANY = "COMPANY", "شرکت"
        COMPANY_ADMIN = "COMPANY_ADMIN", "مدیر شرکت"
        TECHNICIAN = "TECHNICIAN", "تکنسین"
        CUSTOMER = "CUSTOMER", "مشتری"
        CUSTOM = "CUSTOM", "سفارشی"

    class Channel(models.TextChoices):
        INTERNAL = "INTERNAL", "داخلی"
        SMS_FUTURE = "SMS_FUTURE", "پیامک (آینده)"
        EMAIL_FUTURE = "EMAIL_FUTURE", "ایمیل (آینده)"

    class Direction(models.TextChoices):
        INBOUND = "INBOUND", "دریافتی"
        OUTBOUND = "OUTBOUND", "ارسالی"

    class Status(models.TextChoices):
        DRAFT = "DRAFT", "پیش\u200cنویس"
        QUEUED = "QUEUED", "در صف ارسال"
        SENT = "SENT", "ارسال شده"
        FAILED = "FAILED", "ناموفق"
        READ = "READ", "خوانده شده"

    sender = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="sent_platform_messages",
        help_text="Null if system-generated.",
    )
    recipient_user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="received_platform_messages",
    )
    recipient_company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="platform_messages",
    )
    recipient_type = models.CharField(
        max_length=20,
        choices=RecipientType.choices,
        default=RecipientType.COMPANY,
    )
    channel = models.CharField(
        max_length=20,
        choices=Channel.choices,
        default=Channel.INTERNAL,
    )
    direction = models.CharField(
        max_length=10,
        choices=Direction.choices,
        default=Direction.OUTBOUND,
    )
    subject = models.CharField(max_length=300)
    body = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    read_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Platform Message"
        verbose_name_plural = "Platform Messages"

    def __str__(self) -> str:
        return f"{self.subject} ({self.get_status_display()})"



class GlobalSMSPricingSetting(models.Model):
    """Platform-wide SMS pricing. Only one row should exist (singleton)."""
    characters_per_sms = models.PositiveIntegerField(default=60)
    price_per_sms_rial = models.PositiveIntegerField(default=520)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "SMS Pricing Setting"

    def __str__(self):
        return f"{self.price_per_sms_rial} rial/sms, {self.characters_per_sms} chars/sms"


class CompanySMSWallet(models.Model):
    """SMS credit wallet for a tenant company."""
    company = models.OneToOneField("tenants.Company", on_delete=models.CASCADE, related_name="sms_wallet")
    balance_rial = models.BigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company SMS Wallet"

    def __str__(self):
        return f"{self.company.name}: {self.balance_rial} rial"


class CompanySMSTransaction(models.Model):
    """Transaction record for SMS wallet changes."""
    class TransactionType(models.TextChoices):
        CREDIT = "CREDIT", "شارژ"
        DEBIT = "DEBIT", "مصرف"
        ADJUSTMENT = "ADJUSTMENT", "تعدیل"
        BLOCKED = "BLOCKED", "مسدود (اعتبار ناکافی)"

    company = models.ForeignKey("tenants.Company", on_delete=models.CASCADE, related_name="sms_transactions")
    wallet = models.ForeignKey(CompanySMSWallet, on_delete=models.CASCADE, related_name="transactions")
    transaction_type = models.CharField(max_length=15, choices=TransactionType.choices)
    amount_rial = models.BigIntegerField()
    sms_parts = models.PositiveIntegerField(default=0)
    message_length = models.PositiveIntegerField(default=0)
    balance_after = models.BigIntegerField()
    description = models.CharField(max_length=300, blank=True)
    related_invoice = models.ForeignKey("platform_core.PlatformBillingInvoice", on_delete=models.SET_NULL, null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.company.name} {self.transaction_type} {self.amount_rial}"


class PlatformBillingInvoice(models.Model):
    """Invoice from Platform Owner to tenant company."""
    class InvoiceType(models.TextChoices):
        SMS_RECHARGE = "SMS_RECHARGE", "شارژ پیامک"
        SUBSCRIPTION = "SUBSCRIPTION", "اشتراک"
        MANUAL = "MANUAL", "دستی"
        OTHER = "OTHER", "سایر"

    class Status(models.TextChoices):
        UNPAID = "UNPAID", "پرداخت نشده"
        PAID = "PAID", "پرداخت شده"
        CANCELED = "CANCELED", "لغو شده"

    company = models.ForeignKey("tenants.Company", on_delete=models.CASCADE, related_name="platform_invoices")
    invoice_number = models.CharField(max_length=50, unique=True)
    invoice_type = models.CharField(max_length=20, choices=InvoiceType.choices, default=InvoiceType.SMS_RECHARGE)
    amount_rial = models.BigIntegerField()
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.UNPAID)
    description = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="created_platform_invoices")
    paid_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="paid_platform_invoices")
    created_at = models.DateTimeField(auto_now_add=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Invoice #{self.invoice_number} - {self.company.name} ({self.get_status_display()})"



class PlatformPaymentTransaction(models.Model):
    """
    Payment transaction for platform billing invoices.

    Currently supports MANUAL payments only. Future-ready for online
    gateways (ZarinPal, IDPay, PayPing).

    Flow:
    1. Tenant creates recharge invoice (UNPAID)
    2. Payment transaction created (INITIATED)
    3a. Manual: Platform Owner marks paid → VERIFIED
    3b. Future online: redirect to gateway → callback → VERIFIED/FAILED
    4. If VERIFIED: invoice becomes PAID, wallet credited

    TODO (Future):
    - ZarinPal gateway integration
    - IDPay gateway integration
    - PayPing gateway integration
    - Automatic callback verification
    - Refund support
    """

    class Provider(models.TextChoices):
        MANUAL = "MANUAL", "پرداخت دستی"
        ZARINPAL_FUTURE = "ZARINPAL_FUTURE", "زرین‌پال (آینده)"
        IDPAY_FUTURE = "IDPAY_FUTURE", "آیدی‌پی (آینده)"
        PAYPING_FUTURE = "PAYPING_FUTURE", "پی‌پینگ (آینده)"
        OTHER_FUTURE = "OTHER_FUTURE", "سایر (آینده)"

    class Status(models.TextChoices):
        INITIATED = "INITIATED", "آغاز شده"
        REDIRECTED = "REDIRECTED", "هدایت به درگاه"
        PAID = "PAID", "پرداخت شده"
        FAILED = "FAILED", "ناموفق"
        CANCELED = "CANCELED", "لغو شده"
        VERIFIED = "VERIFIED", "تایید شده"

    invoice = models.ForeignKey(
        PlatformBillingInvoice,
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )
    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="platform_payment_transactions",
    )
    amount_rial = models.BigIntegerField()
    provider = models.CharField(
        max_length=20,
        choices=Provider.choices,
        default=Provider.MANUAL,
    )
    authority = models.CharField(max_length=100, blank=True, help_text="Gateway authority/token")
    tracking_code = models.CharField(max_length=100, blank=True)
    reference_id = models.CharField(max_length=100, blank=True)
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.INITIATED,
    )
    gateway_response = models.TextField(blank=True, help_text="Raw gateway response JSON")
    created_at = models.DateTimeField(auto_now_add=True)
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Platform Payment Transaction"

    def __str__(self):
        return f"Payment #{self.id} - {self.invoice.invoice_number} ({self.get_status_display()})"



class CommunicationTemplate(models.Model):
    """
    Platform Owner controlled communication template.
    Tenant companies can ONLY toggle is_enabled for their own company.
    They CANNOT edit text, title, body, links, or placeholders.
    """

    class EventKey(models.TextChoices):
        COMPANY_REGISTERED = "COMPANY_REGISTERED", "ثبت‌نام شرکت"
        COMPANY_APPROVED = "COMPANY_APPROVED", "تأیید شرکت"
        ORDER_CREATED = "ORDER_CREATED", "ایجاد سفارش"
        ORDER_ASSIGNED = "ORDER_ASSIGNED", "تخصیص سفارش"
        ORDER_STATUS_CHANGED = "ORDER_STATUS_CHANGED", "تغییر وضعیت سفارش"
        INVOICE_CREATED = "INVOICE_CREATED", "صدور فاکتور"
        PAYMENT_RECEIVED = "PAYMENT_RECEIVED", "دریافت پرداخت"
        SMS_CREDIT_LOW = "SMS_CREDIT_LOW", "اعتبار پیامک کم"
        SMS_CREDIT_EMPTY = "SMS_CREDIT_EMPTY", "اعتبار پیامک تمام"
        TECHNICIAN_NOTIFICATION = "TECHNICIAN_NOTIFICATION", "اعلان تکنسین"
        OPERATOR_NOTIFICATION = "OPERATOR_NOTIFICATION", "اعلان اپراتور"

    class Channel(models.TextChoices):
        INTERNAL_NOTIFICATION = "INTERNAL_NOTIFICATION", "اعلان داخلی"
        SMS = "SMS", "پیامک"
        EMAIL_FUTURE = "EMAIL_FUTURE", "ایمیل (آینده)"

    class RecipientType(models.TextChoices):
        COMPANY_ADMIN = "COMPANY_ADMIN", "مدیر شرکت"
        OPERATOR = "OPERATOR", "اپراتور"
        TECHNICIAN = "TECHNICIAN", "تکنسین"
        PLATFORM_OWNER = "PLATFORM_OWNER", "مدیر پلتفرم"

    company = models.ForeignKey(
        "tenants.Company", on_delete=models.CASCADE, null=True, blank=True,
        related_name="comm_templates",
        help_text="Null = global default. Set = company-specific override.",
    )
    event_key = models.CharField(max_length=40, choices=EventKey.choices)
    channel = models.CharField(max_length=30, choices=Channel.choices)
    recipient_type = models.CharField(max_length=20, choices=RecipientType.choices)
    title_template = models.CharField(max_length=300)
    body_template = models.TextField()
    action_label = models.CharField(max_length=100, blank=True)
    action_url_template = models.CharField(max_length=300, blank=True)
    is_active = models.BooleanField(default=True)
    is_required = models.BooleanField(default=False)
    allow_company_toggle = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["event_key", "channel"]
        verbose_name = "Communication Template"

    def __str__(self):
        scope = self.company.code if self.company else "GLOBAL"
        return f"[{scope}] {self.get_event_key_display()} / {self.get_channel_display()}"


class CommunicationTemplateCompanySetting(models.Model):
    """Per-company toggle for a communication template."""
    company = models.ForeignKey("tenants.Company", on_delete=models.CASCADE, related_name="comm_template_settings")
    template = models.ForeignKey(CommunicationTemplate, on_delete=models.CASCADE, related_name="company_settings")
    is_enabled = models.BooleanField(default=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["company", "template"], name="unique_comm_tpl_setting_per_company"),
        ]

    def __str__(self):
        return f"{self.company.code} / {self.template.event_key} → {'enabled' if self.is_enabled else 'disabled'}"


class PaymentGatewayProvider(models.TextChoices):
    """Available payment gateway providers."""
    MOCK = "MOCK", "آزمایشی (بدون اتصال)"
    MANUAL = "MANUAL", "پرداخت دستی"
    ZARINPAL_FUTURE = "ZARINPAL_FUTURE", "زرین‌پال (آینده)"
    ZIBAL_FUTURE = "ZIBAL_FUTURE", "زیبال (آینده)"
    IDPAY_FUTURE = "IDPAY_FUTURE", "آیدی‌پی (آینده)"
    PAYPING_FUTURE = "PAYPING_FUTURE", "پی‌پینگ (آینده)"


class PlatformPaymentGatewaySetting(models.Model):
    """
    Payment gateway for Platform Owner (SMS recharge, subscriptions).
    Singleton — only one active setting.
    """
    provider = models.CharField(max_length=20, choices=PaymentGatewayProvider.choices, default=PaymentGatewayProvider.MOCK)
    is_active = models.BooleanField(default=False)
    merchant_id = models.CharField(max_length=200, blank=True, help_text="Merchant ID or API key (masked in UI)")
    terminal_id = models.CharField(max_length=100, blank=True)
    callback_base_url = models.CharField(max_length=300, blank=True, help_text="e.g. https://rastiservice.ir")
    sandbox_mode = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Platform Payment Gateway"

    def __str__(self):
        return f"Platform: {self.get_provider_display()} ({'active' if self.is_active else 'inactive'})"

    @property
    def merchant_id_masked(self):
        if not self.merchant_id or len(self.merchant_id) < 5:
            return "****"
        return "****" + self.merchant_id[-4:]


class CompanyPaymentGatewaySetting(models.Model):
    """
    Payment gateway for a tenant company (order/invoice payments).
    Each company has its own gateway configuration.
    """
    company = models.OneToOneField("tenants.Company", on_delete=models.CASCADE, related_name="payment_gateway")
    provider = models.CharField(max_length=20, choices=PaymentGatewayProvider.choices, default=PaymentGatewayProvider.MOCK)
    is_active = models.BooleanField(default=False)
    merchant_id = models.CharField(max_length=200, blank=True, help_text="Merchant ID or API key (masked in UI)")
    terminal_id = models.CharField(max_length=100, blank=True)
    callback_base_url = models.CharField(max_length=300, blank=True)
    sandbox_mode = models.BooleanField(default=True)
    description = models.TextField(blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Company Payment Gateway"

    def __str__(self):
        return f"{self.company.name}: {self.get_provider_display()}"

    @property
    def merchant_id_masked(self):
        if not self.merchant_id or len(self.merchant_id) < 5:
            return "****"
        return "****" + self.merchant_id[-4:]


# =============================================================================
# PLATFORM SMS OUTBOX AND GLOBAL MESSAGE SETTINGS
# =============================================================================


class PlatformSMSProviderSetting(models.Model):
    class ProviderType(models.TextChoices):
        KAVENEGAR = "kavenegar", "Kavenegar"
        GHASEDAK = "ghasedak", "Ghasedak"
        MELIPAYAMAK = "melipayamak", "MeliPayamak"
        FAKE = "fake", "Fake (Testing)"

    name = models.CharField(max_length=100, default="Platform SMS Provider")
    provider_type = models.CharField(max_length=20, choices=ProviderType.choices, default=ProviderType.FAKE)
    api_key = models.CharField(max_length=300, blank=True)
    sender_number = models.CharField(max_length=20, blank=True)
    is_active = models.BooleanField(default=False)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["id"]
        verbose_name = "Platform SMS Provider Setting"

    def __str__(self):
        return f"{self.name} ({self.provider_type})"


class PlatformSMSMessageTypeSetting(models.Model):
    class Payer(models.TextChoices):
        COMPANY = "COMPANY", "شرکت"
        PLATFORM = "PLATFORM", "مالک پلتفرم"

    class MessageKey(models.TextChoices):
        ORDER_CREATED_ADMIN = "order_created_admin", "سفارش جدید - مدیر شرکت"
        ORDER_AVAILABLE_TECHNICIAN = "order_available_technician", "سفارش جدید - تکنسین‌ها"
        ORDER_ASSIGNED_TECHNICIAN = "order_assigned_technician", "تخصیص سفارش - تکنسین"
        ORDER_ACCEPTED_CUSTOMER = "order_accepted_customer", "پذیرش سفارش - مشتری"
        ORDER_COMPLETED_CUSTOMER = "order_completed_customer", "اتمام سفارش - مشتری"
        ORDER_CANCEL_REQUESTED_ADMIN = "order_cancel_requested_admin", "درخواست لغو - مدیر شرکت"
        ORDER_CANCEL_APPROVED_TECHNICIAN = "order_cancel_approved_technician", "تأیید لغو - تکنسین"
        ORDER_CANCEL_REJECTED_TECHNICIAN = "order_cancel_rejected_technician", "رد لغو - تکنسین"
        INVOICE_ISSUED_CUSTOMER = "invoice_issued_customer", "صدور فاکتور - مشتری"
        PAYMENT_SUCCESS_CUSTOMER = "payment_success_customer", "پرداخت موفق - مشتری"
        PAYMENT_FAILED_CUSTOMER = "payment_failed_customer", "پرداخت ناموفق - مشتری"
        SURVEY_REQUEST_CUSTOMER = "survey_request_customer", "نظرسنجی - مشتری"

        SMS_CREDIT_LOW_ADMIN = "sms_credit_low_admin", "کم بودن اعتبار پیامک - مدیر شرکت"
        SMS_CREDIT_EMPTY_ADMIN = "sms_credit_empty_admin", "اتمام اعتبار پیامک - مدیر شرکت"
        SUBSCRIPTION_EXPIRING_ADMIN = "subscription_expiring_admin", "نزدیک شدن پایان اشتراک - مدیر شرکت"
        SUBSCRIPTION_EXPIRED_ADMIN = "subscription_expired_admin", "پایان اشتراک - مدیر شرکت"
        PLATFORM_PAYMENT_SUCCESS_ADMIN = "platform_payment_success_admin", "پرداخت موفق پلتفرمی - مدیر شرکت"
        PASSWORD_RESET = "password_reset", "بازیابی رمز عبور"

    key = models.CharField(max_length=80, choices=MessageKey.choices, unique=True)
    title = models.CharField(max_length=200)
    payer = models.CharField(max_length=20, choices=Payer.choices, default=Payer.COMPANY)
    is_active = models.BooleanField(default=True)
    default_company_sms_enabled = models.BooleanField(default=True)
    send_start_time = models.TimeField(null=True, blank=True)
    send_end_time = models.TimeField(null=True, blank=True)
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["payer", "key"]
        verbose_name = "Platform SMS Message Type Setting"

    def __str__(self):
        return f"{self.title} ({self.key})"


class PlatformSMSOutbox(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "در صف ارسال"
        SENDING = "sending", "در حال ارسال"
        SENT = "sent", "ارسال شده"
        DELIVERED = "delivered", "ارسال موفق"
        FAILED = "failed", "ارسال ناموفق"
        CANCELLED = "cancelled", "لغو شده"

    recipient_company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="platform_sms_messages",
    )
    provider = models.ForeignKey(
        PlatformSMSProviderSetting,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="outbox_messages",
    )
    template_key = models.CharField(max_length=80, choices=PlatformSMSMessageTypeSetting.MessageKey.choices)
    phone_number = models.CharField(max_length=15)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True)
    provider_message_id = models.CharField(max_length=100, blank=True)
    error_message = models.TextField(blank=True)
    attempt_count = models.PositiveIntegerField(default=0)

    queued_at = models.DateTimeField(auto_now_add=True)
    send_at = models.DateTimeField(null=True, blank=True)
    sending_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    last_attempt_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["status", "send_at"], name="platform_sms_due_idx"),
            models.Index(fields=["recipient_company", "template_key"], name="platform_sms_company_key_idx"),
        ]
        verbose_name = "Platform SMS Outbox"

    def __str__(self):
        return f"Platform SMS to {self.phone_number} ({self.status})"

