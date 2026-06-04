"""Central notification/SMS event catalog.

Defines every business event that can create an in-app notification and,
when enabled, an SMSOutbox row.  This module is intentionally model-free so
it can be imported by models, commands, and services without circular imports.
"""
from __future__ import annotations

from dataclasses import dataclass


class EventKey:
    COMPANY_REGISTERED = "company_registered"
    COMPANY_ACTIVATED = "company_activated"
    COMPANY_REJECTED = "company_rejected"
    COMPANY_ADMIN_LOGIN = "company_admin_login"
    COMPANY_ADMIN_PASSWORD_RESET = "company_admin_password_reset"
    OPERATOR_CREATED = "operator_created"
    TECHNICIAN_CREATED = "technician_created"
    TECHNICIAN_LOGIN = "technician_login"
    TECHNICIAN_STATUS_CHANGED = "technician_status_changed"
    TECHNICIAN_WAGE_PERCENT_CHANGED = "technician_wage_percent_changed"
    SERVICE_CATEGORY_CREATED = "service_category_created"
    SERVICE_ITEM_CREATED = "service_item_created"
    ORDER_CREATED_ADMIN = "order_created_admin"
    ORDER_CREATED_CUSTOMER = "order_created_customer"
    ORDER_AVAILABLE_TECHNICIAN = "order_available_technician"
    ORDER_ASSIGNED_TECHNICIAN = "order_assigned_technician"
    ORDER_ACCEPTED_CUSTOMER = "order_accepted_customer"
    ORDER_REJECTED_TECHNICIAN = "order_rejected_technician"
    ORDER_STARTED = "order_started"
    ORDER_COMPLETED_CUSTOMER = "order_completed_customer"
    ORDER_CANCEL_REQUESTED_CUSTOMER = "order_cancel_requested_customer"
    ORDER_CANCEL_REQUESTED_ADMIN = "order_cancel_requested_admin"
    ORDER_CANCEL_APPROVED_TECHNICIAN = "order_cancel_approved_technician"
    ORDER_CANCEL_REJECTED_TECHNICIAN = "order_cancel_rejected_technician"
    ORDER_CANCELLED = "order_cancelled"
    ORDER_RESCHEDULED = "order_rescheduled"
    INVOICE_CREATED = "invoice_created"
    INVOICE_ISSUED_CUSTOMER = "invoice_issued_customer"
    INVOICE_SENT_CUSTOMER = "invoice_sent_customer"
    INVOICE_PAID_CUSTOMER = "invoice_paid_customer"
    INVOICE_CANCELLED = "invoice_cancelled"
    PAYMENT_STARTED = "payment_started"
    PAYMENT_SUCCESS_CUSTOMER = "payment_success_customer"
    PAYMENT_FAILED_CUSTOMER = "payment_failed_customer"
    WALLET_CHARGED = "wallet_charged"
    SMS_CREDIT_LOW_ADMIN = "sms_credit_low_admin"
    SMS_CREDIT_EMPTY_ADMIN = "sms_credit_empty_admin"
    SMS_TEMPLATE_CHANGE_REQUESTED = "sms_template_change_requested"
    SMS_TEMPLATE_CHANGE_APPROVED = "sms_template_change_approved"
    SMS_TEMPLATE_CHANGE_REJECTED = "sms_template_change_rejected"
    SMS_OUTBOX_FAILED = "sms_outbox_failed"
    SMS_OUTBOX_RETRIED = "sms_outbox_retried"
    SUBSCRIPTION_EXPIRING_ADMIN = "subscription_expiring_admin"
    SUBSCRIPTION_EXPIRED_ADMIN = "subscription_expired_admin"
    PLATFORM_PAYMENT_SUCCESS_ADMIN = "platform_payment_success_admin"
    SURVEY_REQUEST_CUSTOMER = "survey_request_customer"


class Payer:
    COMPANY = "COMPANY"
    PLATFORM = "PLATFORM"


class Recipient:
    CUSTOMER = "CUSTOMER"
    TECHNICIAN = "TECHNICIAN"
    COMPANY_ADMIN = "COMPANY_ADMIN"
    AVAILABLE_TECHNICIANS = "AVAILABLE_TECHNICIANS"
    PLATFORM_OWNER = "PLATFORM_OWNER"
    OPERATOR = "OPERATOR"


@dataclass(frozen=True)
class EventDefinition:
    key: str
    title: str
    recipient: str
    payer: str
    default_sms_enabled: bool
    default_in_app_enabled: bool = True
    sms_supported: bool = True
    template_variables: tuple[str, ...] = ()
    trigger_condition: str = ""
    company_can_disable: bool = True
    company_can_request_text_change: bool = True
    platform_can_edit: bool = True
    description: str = ""


EVENT_DEFINITIONS: dict[str, EventDefinition] = {
    EventKey.COMPANY_REGISTERED: EventDefinition(
        key=EventKey.COMPANY_REGISTERED,
        title='ثبت\u200cنام شرکت جدید',
        recipient=Recipient.PLATFORM_OWNER,
        payer=Payer.PLATFORM,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'company_code', 'admin_name', 'admin_phone'),
        trigger_condition='ثبت شرکت از صفحه /register/',
        description='ثبت شرکت از صفحه /register/',
    ),
    EventKey.COMPANY_ACTIVATED: EventDefinition(
        key=EventKey.COMPANY_ACTIVATED,
        title='فعال\u200cسازی شرکت',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'company_code', 'admin_name'),
        trigger_condition='فعال\u200cسازی شرکت توسط مالک پلتفرم',
        description='فعال\u200cسازی شرکت توسط مالک پلتفرم',
    ),
    EventKey.COMPANY_REJECTED: EventDefinition(
        key=EventKey.COMPANY_REJECTED,
        title='رد شرکت',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'company_code', 'reject_reason'),
        trigger_condition='رد درخواست شرکت توسط مالک پلتفرم',
        description='رد درخواست شرکت توسط مالک پلتفرم',
    ),
    EventKey.COMPANY_ADMIN_LOGIN: EventDefinition(
        key=EventKey.COMPANY_ADMIN_LOGIN,
        title='ورود مدیر شرکت',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=False,
        template_variables=('company_name', 'admin_name', 'login_time'),
        trigger_condition='ورود مدیر شرکت؛ فقط ثبت داخلی',
        description='ورود مدیر شرکت؛ فقط ثبت داخلی',
    ),
    EventKey.COMPANY_ADMIN_PASSWORD_RESET: EventDefinition(
        key=EventKey.COMPANY_ADMIN_PASSWORD_RESET,
        title='بازنشانی رمز عبور مدیر',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'admin_name', 'reset_code'),
        trigger_condition='درخواست بازنشانی رمز عبور مدیر شرکت',
        description='درخواست بازنشانی رمز عبور مدیر شرکت',
    ),
    EventKey.OPERATOR_CREATED: EventDefinition(
        key=EventKey.OPERATOR_CREATED,
        title='ایجاد اپراتور',
        recipient=Recipient.OPERATOR,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'operator_name', 'operator_username'),
        trigger_condition='ایجاد اپراتور شرکت',
        description='ایجاد اپراتور شرکت',
    ),
    EventKey.TECHNICIAN_CREATED: EventDefinition(
        key=EventKey.TECHNICIAN_CREATED,
        title='ایجاد نیروی خدماتی',
        recipient=Recipient.TECHNICIAN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'technician_name', 'technician_username'),
        trigger_condition='ایجاد نیروی خدماتی',
        description='ایجاد نیروی خدماتی',
    ),
    EventKey.TECHNICIAN_LOGIN: EventDefinition(
        key=EventKey.TECHNICIAN_LOGIN,
        title='ورود نیروی خدماتی',
        recipient=Recipient.TECHNICIAN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=False,
        template_variables=('company_name', 'technician_name', 'login_time'),
        trigger_condition='ورود نیروی خدماتی؛ فقط ثبت داخلی',
        description='ورود نیروی خدماتی؛ فقط ثبت داخلی',
    ),
    EventKey.TECHNICIAN_STATUS_CHANGED: EventDefinition(
        key=EventKey.TECHNICIAN_STATUS_CHANGED,
        title='تغییر وضعیت نیروی خدماتی',
        recipient=Recipient.TECHNICIAN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'technician_name', 'new_status'),
        trigger_condition='تغییر وضعیت فعال/غیرفعال یا آماده\u200cبه\u200cکار',
        description='تغییر وضعیت فعال/غیرفعال یا آماده\u200cبه\u200cکار',
    ),
    EventKey.TECHNICIAN_WAGE_PERCENT_CHANGED: EventDefinition(
        key=EventKey.TECHNICIAN_WAGE_PERCENT_CHANGED,
        title='تغییر درصد اجرت نیرو',
        recipient=Recipient.TECHNICIAN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'technician_name', 'old_percent', 'new_percent'),
        trigger_condition='تغییر درصد اجرت نیروی خدماتی',
        description='تغییر درصد اجرت نیروی خدماتی',
    ),
    EventKey.SERVICE_CATEGORY_CREATED: EventDefinition(
        key=EventKey.SERVICE_CATEGORY_CREATED,
        title='ایجاد رسته خدمات',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'service_category'),
        trigger_condition='ایجاد رسته خدمات توسط مدیر شرکت',
        description='ایجاد رسته خدمات توسط مدیر شرکت',
    ),
    EventKey.SERVICE_ITEM_CREATED: EventDefinition(
        key=EventKey.SERVICE_ITEM_CREATED,
        title='ایجاد آیتم خدمات',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'service_category', 'service_item'),
        trigger_condition='ایجاد آیتم/خدمت پایه',
        description='ایجاد آیتم/خدمت پایه',
    ),
    EventKey.ORDER_CREATED_ADMIN: EventDefinition(
        key=EventKey.ORDER_CREATED_ADMIN,
        title='سفارش جدید - مدیر شرکت',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name', 'customer_phone', 'service_category'),
        trigger_condition='ثبت سفارش برای اطلاع مدیر شرکت',
        description='ثبت سفارش برای اطلاع مدیر شرکت',
    ),
    EventKey.ORDER_CREATED_CUSTOMER: EventDefinition(
        key=EventKey.ORDER_CREATED_CUSTOMER,
        title='سفارش جدید - مشتری',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name', 'service_category'),
        trigger_condition='ثبت سفارش برای اطلاع مشتری',
        description='ثبت سفارش برای اطلاع مشتری',
    ),
    EventKey.ORDER_AVAILABLE_TECHNICIAN: EventDefinition(
        key=EventKey.ORDER_AVAILABLE_TECHNICIAN,
        title='سفارش جدید برای نیروها',
        recipient=Recipient.AVAILABLE_TECHNICIANS,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'service_category', 'customer_name'),
        trigger_condition='قابل مشاهده شدن سفارش برای نیروهای واجد شرایط',
        description='قابل مشاهده شدن سفارش برای نیروهای واجد شرایط',
    ),
    EventKey.ORDER_ASSIGNED_TECHNICIAN: EventDefinition(
        key=EventKey.ORDER_ASSIGNED_TECHNICIAN,
        title='تخصیص سفارش به نیرو',
        recipient=Recipient.TECHNICIAN,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name', 'customer_phone', 'technician_name'),
        trigger_condition='تخصیص سفارش به نیروی خدماتی',
        description='تخصیص سفارش به نیروی خدماتی',
    ),
    EventKey.ORDER_ACCEPTED_CUSTOMER: EventDefinition(
        key=EventKey.ORDER_ACCEPTED_CUSTOMER,
        title='پذیرش سفارش - مشتری',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name', 'technician_name', 'technician_phone', 'service_category'),
        trigger_condition='پذیرش سفارش توسط نیرو',
        description='پذیرش سفارش توسط نیرو',
    ),
    EventKey.ORDER_REJECTED_TECHNICIAN: EventDefinition(
        key=EventKey.ORDER_REJECTED_TECHNICIAN,
        title='رد سفارش توسط نیرو',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=False,
        template_variables=('company_name', 'order_id', 'technician_name', 'reject_reason'),
        trigger_condition='فعلاً جریان قطعی در سیستم ندارد',
        description='فعلاً جریان قطعی در سیستم ندارد',
    ),
    EventKey.ORDER_STARTED: EventDefinition(
        key=EventKey.ORDER_STARTED,
        title='شروع سفارش',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name', 'technician_name'),
        trigger_condition='شروع انجام سفارش توسط نیرو',
        description='شروع انجام سفارش توسط نیرو',
    ),
    EventKey.ORDER_COMPLETED_CUSTOMER: EventDefinition(
        key=EventKey.ORDER_COMPLETED_CUSTOMER,
        title='اتمام سفارش - مشتری',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name', 'technician_name'),
        trigger_condition='اتمام سفارش',
        description='اتمام سفارش',
    ),
    EventKey.ORDER_CANCEL_REQUESTED_CUSTOMER: EventDefinition(
        key=EventKey.ORDER_CANCEL_REQUESTED_CUSTOMER,
        title='درخواست لغو توسط مشتری',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name', 'cancel_reason'),
        trigger_condition='درخواست لغو سفارش توسط مشتری',
        description='درخواست لغو سفارش توسط مشتری',
    ),
    EventKey.ORDER_CANCEL_REQUESTED_ADMIN: EventDefinition(
        key=EventKey.ORDER_CANCEL_REQUESTED_ADMIN,
        title='درخواست لغو سفارش - مدیر',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'technician_name', 'customer_name', 'cancel_reason'),
        trigger_condition='درخواست لغو سفارش توسط نیروی خدماتی',
        description='درخواست لغو سفارش توسط نیروی خدماتی',
    ),
    EventKey.ORDER_CANCEL_APPROVED_TECHNICIAN: EventDefinition(
        key=EventKey.ORDER_CANCEL_APPROVED_TECHNICIAN,
        title='تأیید لغو - نیرو',
        recipient=Recipient.TECHNICIAN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'technician_name'),
        trigger_condition='تأیید درخواست لغو',
        description='تأیید درخواست لغو',
    ),
    EventKey.ORDER_CANCEL_REJECTED_TECHNICIAN: EventDefinition(
        key=EventKey.ORDER_CANCEL_REJECTED_TECHNICIAN,
        title='رد لغو - نیرو',
        recipient=Recipient.TECHNICIAN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'technician_name'),
        trigger_condition='رد درخواست لغو',
        description='رد درخواست لغو',
    ),
    EventKey.ORDER_CANCELLED: EventDefinition(
        key=EventKey.ORDER_CANCELLED,
        title='لغو سفارش',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name', 'cancel_reason'),
        trigger_condition='لغو قطعی سفارش',
        description='لغو قطعی سفارش',
    ),
    EventKey.ORDER_RESCHEDULED: EventDefinition(
        key=EventKey.ORDER_RESCHEDULED,
        title='تغییر زمان سفارش',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name', 'new_date'),
        trigger_condition='تغییر تاریخ/زمان سفارش',
        description='تغییر تاریخ/زمان سفارش',
    ),
    EventKey.INVOICE_CREATED: EventDefinition(
        key=EventKey.INVOICE_CREATED,
        title='ایجاد فاکتور',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=False,
        template_variables=('company_name', 'invoice_number', 'order_id', 'customer_name'),
        trigger_condition='ایجاد پیش\u200cنویس فاکتور؛ داخلی',
        description='ایجاد پیش\u200cنویس فاکتور؛ داخلی',
    ),
    EventKey.INVOICE_ISSUED_CUSTOMER: EventDefinition(
        key=EventKey.INVOICE_ISSUED_CUSTOMER,
        title='صدور فاکتور - مشتری',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'invoice_number', 'invoice_amount', 'customer_name', 'public_invoice_url'),
        trigger_condition='صدور فاکتور برای مشتری',
        description='صدور فاکتور برای مشتری',
    ),
    EventKey.INVOICE_SENT_CUSTOMER: EventDefinition(
        key=EventKey.INVOICE_SENT_CUSTOMER,
        title='ارسال فاکتور - مشتری',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'invoice_number', 'customer_name', 'public_invoice_url'),
        trigger_condition='ارسال لینک فاکتور برای مشتری',
        description='ارسال لینک فاکتور برای مشتری',
    ),
    EventKey.INVOICE_PAID_CUSTOMER: EventDefinition(
        key=EventKey.INVOICE_PAID_CUSTOMER,
        title='پرداخت فاکتور - مشتری',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'invoice_number', 'invoice_amount', 'customer_name'),
        trigger_condition='ثبت پرداخت فاکتور',
        description='ثبت پرداخت فاکتور',
    ),
    EventKey.INVOICE_CANCELLED: EventDefinition(
        key=EventKey.INVOICE_CANCELLED,
        title='لغو فاکتور',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=False,
        template_variables=('company_name', 'invoice_number', 'customer_name'),
        trigger_condition='لغو فاکتور؛ داخلی',
        description='لغو فاکتور؛ داخلی',
    ),
    EventKey.PAYMENT_STARTED: EventDefinition(
        key=EventKey.PAYMENT_STARTED,
        title='شروع پرداخت',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=False,
        template_variables=('company_name', 'invoice_number', 'customer_name'),
        trigger_condition='شروع پرداخت؛ وضعیت موقت',
        description='شروع پرداخت؛ وضعیت موقت',
    ),
    EventKey.PAYMENT_SUCCESS_CUSTOMER: EventDefinition(
        key=EventKey.PAYMENT_SUCCESS_CUSTOMER,
        title='پرداخت موفق - مشتری',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'invoice_number', 'invoice_amount', 'customer_name'),
        trigger_condition='پرداخت موفق',
        description='پرداخت موفق',
    ),
    EventKey.PAYMENT_FAILED_CUSTOMER: EventDefinition(
        key=EventKey.PAYMENT_FAILED_CUSTOMER,
        title='پرداخت ناموفق - مشتری',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'invoice_number', 'customer_name', 'public_invoice_url'),
        trigger_condition='پرداخت ناموفق',
        description='پرداخت ناموفق',
    ),
    EventKey.WALLET_CHARGED: EventDefinition(
        key=EventKey.WALLET_CHARGED,
        title='شارژ کیف پول پیامک',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'charged_amount', 'new_balance'),
        trigger_condition='شارژ کیف پول پیامک',
        description='شارژ کیف پول پیامک',
    ),
    EventKey.SMS_CREDIT_LOW_ADMIN: EventDefinition(
        key=EventKey.SMS_CREDIT_LOW_ADMIN,
        title='کم بودن اعتبار پیامک',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'remaining_balance'),
        trigger_condition='هشدار کم بودن اعتبار پیامک',
        description='هشدار کم بودن اعتبار پیامک',
    ),
    EventKey.SMS_CREDIT_EMPTY_ADMIN: EventDefinition(
        key=EventKey.SMS_CREDIT_EMPTY_ADMIN,
        title='اتمام اعتبار پیامک',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name',),
        trigger_condition='هشدار اتمام اعتبار پیامک',
        description='هشدار اتمام اعتبار پیامک',
    ),
    EventKey.SMS_TEMPLATE_CHANGE_REQUESTED: EventDefinition(
        key=EventKey.SMS_TEMPLATE_CHANGE_REQUESTED,
        title='درخواست تغییر قالب پیامک',
        recipient=Recipient.PLATFORM_OWNER,
        payer=Payer.PLATFORM,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'event_key', 'template_title'),
        trigger_condition='درخواست تغییر متن پیامک توسط شرکت',
        description='درخواست تغییر متن پیامک توسط شرکت',
    ),
    EventKey.SMS_TEMPLATE_CHANGE_APPROVED: EventDefinition(
        key=EventKey.SMS_TEMPLATE_CHANGE_APPROVED,
        title='تأیید تغییر قالب پیامک',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'event_key', 'template_title'),
        trigger_condition='تأیید درخواست تغییر متن پیامک',
        description='تأیید درخواست تغییر متن پیامک',
    ),
    EventKey.SMS_TEMPLATE_CHANGE_REJECTED: EventDefinition(
        key=EventKey.SMS_TEMPLATE_CHANGE_REJECTED,
        title='رد تغییر قالب پیامک',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'event_key', 'template_title', 'reject_reason'),
        trigger_condition='رد درخواست تغییر متن پیامک',
        description='رد درخواست تغییر متن پیامک',
    ),
    EventKey.SMS_OUTBOX_FAILED: EventDefinition(
        key=EventKey.SMS_OUTBOX_FAILED,
        title='خطا در ارسال پیامک',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'phone_number', 'error_message'),
        trigger_condition='خطا در پردازش پیامک',
        description='خطا در پردازش پیامک',
    ),
    EventKey.SMS_OUTBOX_RETRIED: EventDefinition(
        key=EventKey.SMS_OUTBOX_RETRIED,
        title='تلاش مجدد ارسال پیامک',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=False,
        template_variables=('company_name', 'phone_number'),
        trigger_condition='ثبت داخلی تلاش مجدد پیامک',
        description='ثبت داخلی تلاش مجدد پیامک',
    ),
    EventKey.SUBSCRIPTION_EXPIRING_ADMIN: EventDefinition(
        key=EventKey.SUBSCRIPTION_EXPIRING_ADMIN,
        title='نزدیک شدن پایان اشتراک',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'expiry_date', 'days_remaining'),
        trigger_condition='هشدار نزدیک شدن پایان اشتراک',
        description='هشدار نزدیک شدن پایان اشتراک',
    ),
    EventKey.SUBSCRIPTION_EXPIRED_ADMIN: EventDefinition(
        key=EventKey.SUBSCRIPTION_EXPIRED_ADMIN,
        title='پایان اشتراک',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name',),
        trigger_condition='پایان اشتراک',
        description='پایان اشتراک',
    ),
    EventKey.PLATFORM_PAYMENT_SUCCESS_ADMIN: EventDefinition(
        key=EventKey.PLATFORM_PAYMENT_SUCCESS_ADMIN,
        title='پرداخت موفق پلتفرمی',
        recipient=Recipient.COMPANY_ADMIN,
        payer=Payer.PLATFORM,
        default_sms_enabled=True,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'amount', 'invoice_number'),
        trigger_condition='پرداخت موفق فاکتور پلتفرم',
        description='پرداخت موفق فاکتور پلتفرم',
    ),
    EventKey.SURVEY_REQUEST_CUSTOMER: EventDefinition(
        key=EventKey.SURVEY_REQUEST_CUSTOMER,
        title='نظرسنجی - مشتری',
        recipient=Recipient.CUSTOMER,
        payer=Payer.COMPANY,
        default_sms_enabled=False,
        default_in_app_enabled=True,
        sms_supported=True,
        template_variables=('company_name', 'order_id', 'customer_name'),
        trigger_condition='درخواست ثبت نظر پس از اتمام سفارش',
        description='درخواست ثبت نظر پس از اتمام سفارش',
    ),
}


def get_event_definition(event_key: str) -> EventDefinition | None:
    return EVENT_DEFINITIONS.get(str(event_key or "").strip())


def get_all_event_keys() -> list[str]:
    return list(EVENT_DEFINITIONS.keys())


def get_sms_supported_events() -> list[EventDefinition]:
    return [event for event in EVENT_DEFINITIONS.values() if event.sms_supported]


def get_internal_only_events() -> list[EventDefinition]:
    return [event for event in EVENT_DEFINITIONS.values() if not event.sms_supported]


def get_sms_supported_event_keys() -> list[str]:
    return [event.key for event in get_sms_supported_events()]
