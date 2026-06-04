from django.conf import settings
"""
Notifications - Models.

Tenant-scoped in-app notification system.
All notifications MUST be filtered by company.
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class Notification(CompanyOwnedModel):
    """
    In-app notification for company users.

    Types:
    - ORDER_CREATED: Admin/staff notified of new order
    - ORDER_ACCEPTED: Customer notified technician accepted
    - ORDER_COMPLETED: Customer notified order is done
    - INVOICE_ISSUED: Customer notified invoice ready
    - PAYMENT_PAID: Customer + admin notified payment succeeded
    - PAYMENT_FAILED: Customer notified payment failed
    """

    class NotificationType(models.TextChoices):
        ORDER_CREATED = "order_created", "Order Created"
        ORDER_AVAILABLE = "order_available", "Order Available"
        ORDER_ASSIGNED = "order_assigned", "Order Assigned"
        ORDER_ACCEPTED = "order_accepted", "Order Accepted"
        ORDER_COMPLETED = "order_completed", "Order Completed"
        ORDER_CANCEL_REQUESTED = "order_cancel_requested", "Order Cancel Requested"
        ORDER_CANCEL_APPROVED = "order_cancel_approved", "Order Cancel Approved"
        ORDER_CANCEL_REJECTED = "order_cancel_rejected", "Order Cancel Rejected"
        INVOICE_ISSUED = "invoice_issued", "Invoice Issued"
        PAYMENT_PAID = "payment_paid", "Payment Paid"
        PAYMENT_FAILED = "payment_failed", "Payment Failed"

    recipient = models.ForeignKey(
        "accounts.CompanyUser",
        on_delete=models.CASCADE,
        related_name="notifications",
    )
    notification_type = models.CharField(
        max_length=30,
        choices=NotificationType.choices,
    )
    title = models.CharField(max_length=200)
    message = models.TextField()
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)

    # Optional references to related objects
    related_order = models.ForeignKey(
        "orders.Order",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )
    related_invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notifications",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "recipient", "is_read"]),
        ]

    def __str__(self) -> str:
        return f"{self.title} → {self.recipient}"



class NotificationSetting(CompanyOwnedModel):
    """
    Per-company switches for in-app notifications and SMS notifications.

    Each row controls one business event, for example:
    - new order
    - technician assignment
    - cancel request
    - cancel approved/rejected
    - invoice/payment events

    The setting is intentionally separate from SMS templates:
    - NotificationSetting controls whether an event is allowed to send.
    - SMSTemplate controls the SMS wording and SMS active/inactive state.
    """

    class EventKey(models.TextChoices):
        COMPANY_REGISTERED = 'company_registered', 'ثبت\u200cنام شرکت جدید'
        COMPANY_ACTIVATED = 'company_activated', 'فعال\u200cسازی شرکت'
        COMPANY_REJECTED = 'company_rejected', 'رد شرکت'
        COMPANY_ADMIN_LOGIN = 'company_admin_login', 'ورود مدیر شرکت'
        COMPANY_ADMIN_PASSWORD_RESET = 'company_admin_password_reset', 'بازنشانی رمز عبور مدیر'
        OPERATOR_CREATED = 'operator_created', 'ایجاد اپراتور'
        TECHNICIAN_CREATED = 'technician_created', 'ایجاد نیروی خدماتی'
        TECHNICIAN_LOGIN = 'technician_login', 'ورود نیروی خدماتی'
        TECHNICIAN_STATUS_CHANGED = 'technician_status_changed', 'تغییر وضعیت نیروی خدماتی'
        TECHNICIAN_WAGE_PERCENT_CHANGED = 'technician_wage_percent_changed', 'تغییر درصد اجرت نیرو'
        SERVICE_CATEGORY_CREATED = 'service_category_created', 'ایجاد رسته خدمات'
        SERVICE_ITEM_CREATED = 'service_item_created', 'ایجاد آیتم خدمات'
        ORDER_CREATED_ADMIN = 'order_created_admin', 'سفارش جدید - مدیر شرکت'
        ORDER_CREATED_CUSTOMER = 'order_created_customer', 'سفارش جدید - مشتری'
        ORDER_AVAILABLE_TECHNICIAN = 'order_available_technician', 'سفارش جدید برای نیروها'
        ORDER_ASSIGNED_TECHNICIAN = 'order_assigned_technician', 'تخصیص سفارش به نیرو'
        ORDER_ACCEPTED_CUSTOMER = 'order_accepted_customer', 'پذیرش سفارش - مشتری'
        ORDER_REJECTED_TECHNICIAN = 'order_rejected_technician', 'رد سفارش توسط نیرو'
        ORDER_STARTED = 'order_started', 'شروع سفارش'
        ORDER_COMPLETED_CUSTOMER = 'order_completed_customer', 'اتمام سفارش - مشتری'
        ORDER_CANCEL_REQUESTED_CUSTOMER = 'order_cancel_requested_customer', 'درخواست لغو توسط مشتری'
        ORDER_CANCEL_REQUESTED_ADMIN = 'order_cancel_requested_admin', 'درخواست لغو سفارش - مدیر'
        ORDER_CANCEL_APPROVED_TECHNICIAN = 'order_cancel_approved_technician', 'تأیید لغو - نیرو'
        ORDER_CANCEL_REJECTED_TECHNICIAN = 'order_cancel_rejected_technician', 'رد لغو - نیرو'
        ORDER_CANCELLED = 'order_cancelled', 'لغو سفارش'
        ORDER_RESCHEDULED = 'order_rescheduled', 'تغییر زمان سفارش'
        INVOICE_CREATED = 'invoice_created', 'ایجاد فاکتور'
        INVOICE_ISSUED_CUSTOMER = 'invoice_issued_customer', 'صدور فاکتور - مشتری'
        INVOICE_SENT_CUSTOMER = 'invoice_sent_customer', 'ارسال فاکتور - مشتری'
        INVOICE_PAID_CUSTOMER = 'invoice_paid_customer', 'پرداخت فاکتور - مشتری'
        INVOICE_CANCELLED = 'invoice_cancelled', 'لغو فاکتور'
        PAYMENT_STARTED = 'payment_started', 'شروع پرداخت'
        PAYMENT_SUCCESS_CUSTOMER = 'payment_success_customer', 'پرداخت موفق - مشتری'
        PAYMENT_FAILED_CUSTOMER = 'payment_failed_customer', 'پرداخت ناموفق - مشتری'
        WALLET_CHARGED = 'wallet_charged', 'شارژ کیف پول پیامک'
        SMS_CREDIT_LOW_ADMIN = 'sms_credit_low_admin', 'کم بودن اعتبار پیامک'
        SMS_CREDIT_EMPTY_ADMIN = 'sms_credit_empty_admin', 'اتمام اعتبار پیامک'
        SMS_TEMPLATE_CHANGE_REQUESTED = 'sms_template_change_requested', 'درخواست تغییر قالب پیامک'
        SMS_TEMPLATE_CHANGE_APPROVED = 'sms_template_change_approved', 'تأیید تغییر قالب پیامک'
        SMS_TEMPLATE_CHANGE_REJECTED = 'sms_template_change_rejected', 'رد تغییر قالب پیامک'
        SMS_OUTBOX_FAILED = 'sms_outbox_failed', 'خطا در ارسال پیامک'
        SMS_OUTBOX_RETRIED = 'sms_outbox_retried', 'تلاش مجدد ارسال پیامک'
        SUBSCRIPTION_EXPIRING_ADMIN = 'subscription_expiring_admin', 'نزدیک شدن پایان اشتراک'
        SUBSCRIPTION_EXPIRED_ADMIN = 'subscription_expired_admin', 'پایان اشتراک'
        PLATFORM_PAYMENT_SUCCESS_ADMIN = 'platform_payment_success_admin', 'پرداخت موفق پلتفرمی'
        SURVEY_REQUEST_CUSTOMER = 'survey_request_customer', 'نظرسنجی - مشتری'


    event_key = models.CharField(max_length=80, choices=EventKey.choices)
    title = models.CharField(max_length=200, blank=True)
    in_app_enabled = models.BooleanField(default=True)
    sms_enabled = models.BooleanField(default=True)

    class Meta:
        ordering = ["event_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "event_key"],
                name="unique_notification_setting_per_company_event",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company} - {self.event_key}"


class NotificationEvent(models.Model):
    """Audit trail for business events and their notification dispatch result."""

    class Status(models.TextChoices):
        RECORDED = "recorded", "ثبت شده"
        DISPATCHED = "dispatched", "پردازش شده"
        SKIPPED = "skipped", "رد شده"
        FAILED = "failed", "ناموفق"

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="notification_events",
    )
    event_key = models.CharField(max_length=100, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notification_events",
    )

    target_app = models.CharField(max_length=100, blank=True)
    target_model = models.CharField(max_length=100, blank=True)
    target_id = models.PositiveIntegerField(null=True, blank=True)

    payload_json = models.JSONField(default=dict, blank=True)
    dedup_key = models.CharField(max_length=255, blank=True, db_index=True)

    status = models.CharField(max_length=20, choices=Status.choices, default=Status.RECORDED, db_index=True)
    result_message = models.TextField(blank=True)
    dispatched_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "event_key", "created_at"], name="notif_event_company_key_idx"),
            models.Index(fields=["target_app", "target_model", "target_id"], name="notif_event_target_idx"),
        ]

    def __str__(self):
        return f"{self.event_key} ({self.status})"

