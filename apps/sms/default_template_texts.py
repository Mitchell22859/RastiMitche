"""Central default SMS template catalog.

All default Persian SMS texts for SMS-supported events live here.
Seed commands, master-template sync, and company provisioning should read from
this file instead of keeping local hard-coded copies.
"""
from __future__ import annotations

from apps.notifications.event_catalog import EVENT_DEFINITIONS, get_sms_supported_event_keys


SMS_DEFAULT_TEMPLATES: dict[str, dict] = {
    'company_registered': {
        "event_key": 'company_registered',
        "title": 'ثبت\u200cنام شرکت جدید',
        "recipient_type": 'platform_admin',
        "scope": 'platform',
        "template_variables": ['company_name', 'company_code', 'admin_name', 'admin_phone'],
        "template_text": 'ثبت\u200cنام شرکت جدید در پلتفرم انجام شد.\nنام شرکت: {{ company_name }}\nکد شرکت: {{ company_code }}\nمدیر: {{ admin_name }}\nموبایل: {{ admin_phone }}',
        "default_sms_enabled": False,
    },
    'company_activated': {
        "event_key": 'company_activated',
        "title": 'فعال\u200cسازی شرکت',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'company_code', 'admin_name'],
        "template_text": '«{{ company_name }}»\nمدیر گرامی {{ admin_name }} عزیز\nشرکت شما با کد {{ company_code }} فعال شد و اکنون می\u200cتوانید از پنل استفاده کنید.',
        "default_sms_enabled": True,
    },
    'company_rejected': {
        "event_key": 'company_rejected',
        "title": 'رد شرکت',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'company_code', 'reject_reason'],
        "template_text": '«{{ company_name }}»\nرد شرکت',
        "default_sms_enabled": True,
    },
    'company_admin_login': {
        "event_key": 'company_admin_login',
        "title": 'ورود مدیر شرکت',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'admin_name', 'login_time'],
        "template_text": '«{{ company_name }}»\nورود مدیر {{ admin_name }} به پنل ثبت شد.',
        "default_sms_enabled": False,
    },
    'company_admin_password_reset': {
        "event_key": 'company_admin_password_reset',
        "title": 'بازنشانی رمز عبور مدیر',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'admin_name', 'reset_code'],
        "template_text": '«{{ company_name }}»\nکد بازیابی رمز عبور شما: {{ otp_code }}\nاعتبار: ۲ دقیقه',
        "default_sms_enabled": True,
    },
    'company_user_password_reset': {
        "event_key": 'company_user_password_reset',
        "title": 'بازیابی رمز عبور کاربر شرکت',
        "recipient_type": 'company_user',
        "scope": 'company',
        "template_variables": ['company_name', 'otp_code'],
        "template_text": '«{{ company_name }}»\nکد بازیابی رمز عبور شما: {{ otp_code }}\nاعتبار: ۲ دقیقه',
        "default_sms_enabled": True,
    },
    'operator_created': {
        "event_key": 'operator_created',
        "title": 'ایجاد اپراتور',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'operator_name', 'operator_username'],
        "template_text": '«{{ company_name }}»\nایجاد اپراتور',
        "default_sms_enabled": False,
    },
    'technician_created': {
        "event_key": 'technician_created',
        "title": 'ایجاد نیروی خدماتی',
        "recipient_type": 'technician',
        "scope": 'company',
        "template_variables": ['company_name', 'technician_name', 'technician_username'],
        "template_text": '«{{ company_name }}»\nایجاد نیروی خدماتی\nنیروی خدماتی: {{ technician_name }}',
        "default_sms_enabled": False,
    },
    'technician_login': {
        "event_key": 'technician_login',
        "title": 'ورود نیروی خدماتی',
        "recipient_type": 'technician',
        "scope": 'company',
        "template_variables": ['company_name', 'technician_name', 'login_time'],
        "template_text": '«{{ company_name }}»\nورود نیروی خدماتی {{ technician_name }} به سیستم ثبت شد.',
        "default_sms_enabled": False,
    },
    'technician_status_changed': {
        "event_key": 'technician_status_changed',
        "title": 'تغییر وضعیت نیروی خدماتی',
        "recipient_type": 'technician',
        "scope": 'company',
        "template_variables": ['company_name', 'technician_name', 'new_status'],
        "template_text": '«{{ company_name }}»\nتغییر وضعیت نیروی خدماتی\nنیروی خدماتی: {{ technician_name }}',
        "default_sms_enabled": False,
    },
    'technician_wage_percent_changed': {
        "event_key": 'technician_wage_percent_changed',
        "title": 'تغییر درصد اجرت نیرو',
        "recipient_type": 'technician',
        "scope": 'company',
        "template_variables": ['company_name', 'technician_name', 'old_percent', 'new_percent'],
        "template_text": '«{{ company_name }}»\nتغییر درصد اجرت نیرو\nنیروی خدماتی: {{ technician_name }}',
        "default_sms_enabled": False,
    },
    'service_category_created': {
        "event_key": 'service_category_created',
        "title": 'ایجاد رسته خدمات',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'service_category'],
        "template_text": '«{{ company_name }}»\nایجاد رسته خدمات\nرسته: {{ service_category }}\nآیتم: {{ service_item }}',
        "default_sms_enabled": False,
    },
    'service_item_created': {
        "event_key": 'service_item_created',
        "title": 'ایجاد آیتم خدمات',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'service_category', 'service_item'],
        "template_text": '«{{ company_name }}»\nایجاد آیتم خدمات\nرسته: {{ service_category }}\nآیتم: {{ service_item }}',
        "default_sms_enabled": False,
    },
    'order_created_admin': {
        "event_key": 'order_created_admin',
        "title": 'سفارش جدید - مدیر شرکت',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name', 'customer_phone', 'service_category'],
        "template_text": '«{{ company_name }}»\nسفارش جدید - مدیر شرکت\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": False,
    },
    'order_created_customer': {
        "event_key": 'order_created_customer',
        "title": 'سفارش جدید - مشتری',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name', 'service_category'],
        "template_text": '«{{ company_name }}»\nسفارش جدید - مشتری\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": False,
    },
    'order_available_technician': {
        "event_key": 'order_available_technician',
        "title": 'سفارش جدید برای نیروها',
        "recipient_type": 'technician',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'service_category', 'customer_name'],
        "template_text": '«{{ company_name }}»\nسفارش جدید برای نیروها\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": False,
    },
    'order_assigned_technician': {
        "event_key": 'order_assigned_technician',
        "title": 'تخصیص سفارش به نیرو',
        "recipient_type": 'technician',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name', 'customer_phone', 'technician_name'],
        "template_text": '«{{ company_name }}»\nتخصیص سفارش به نیرو\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": True,
    },
    'order_accepted_customer': {
        "event_key": 'order_accepted_customer',
        "title": 'پذیرش سفارش - مشتری',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name', 'technician_name', 'technician_phone', 'service_category'],
        "template_text": '«{{ company_name }}»\nمشتری گرامی {{ customer_name }} عزیز\nسفارش شما «{{ service_category }}» توسط تکنسین تأیید شد.\n- شماره سفارش: {{ order_id }}\n- نام تکنسین: {{ technician_name }}\n- شماره تماس: {{ technician_phone }}\nلطفاً ساعت مراجعه را با ایشان هماهنگ نمایید.',
        "default_sms_enabled": True,
    },
    'order_rejected_technician': {
        "event_key": 'order_rejected_technician',
        "title": 'رد سفارش توسط نیرو',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'technician_name', 'reject_reason'],
        "template_text": '«{{ company_name }}»\nسفارش {{ order_id }} توسط نیرو رد شد.\nنیرو: {{ technician_name }}',
        "default_sms_enabled": False,
    },
    'order_started': {
        "event_key": 'order_started',
        "title": 'شروع سفارش',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name', 'technician_name'],
        "template_text": '«{{ company_name }}»\nشروع سفارش\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": False,
    },
    'order_completed_customer': {
        "event_key": 'order_completed_customer',
        "title": 'اتمام سفارش - مشتری',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name', 'technician_name'],
        "template_text": '«{{ company_name }}»\nاتمام سفارش - مشتری\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": True,
    },
    'order_cancel_requested_customer': {
        "event_key": 'order_cancel_requested_customer',
        "title": 'درخواست لغو توسط مشتری',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name', 'cancel_reason'],
        "template_text": '«{{ company_name }}»\nدرخواست لغو توسط مشتری\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": False,
    },
    'order_cancel_requested_admin': {
        "event_key": 'order_cancel_requested_admin',
        "title": 'درخواست لغو سفارش - مدیر',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'technician_name', 'customer_name', 'cancel_reason'],
        "template_text": '«{{ company_name }}»\nدرخواست لغو سفارش - مدیر\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": True,
    },
    'order_cancel_approved_technician': {
        "event_key": 'order_cancel_approved_technician',
        "title": 'تأیید لغو - نیرو',
        "recipient_type": 'technician',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'technician_name'],
        "template_text": '«{{ company_name }}»\nتأیید لغو - نیرو\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": False,
    },
    'order_cancel_rejected_technician': {
        "event_key": 'order_cancel_rejected_technician',
        "title": 'رد لغو - نیرو',
        "recipient_type": 'technician',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'technician_name'],
        "template_text": '«{{ company_name }}»\nرد لغو - نیرو\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": False,
    },
    'order_cancelled': {
        "event_key": 'order_cancelled',
        "title": 'لغو سفارش',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name', 'cancel_reason'],
        "template_text": '«{{ company_name }}»\nلغو سفارش\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": False,
    },
    'order_rescheduled': {
        "event_key": 'order_rescheduled',
        "title": 'تغییر زمان سفارش',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name', 'new_date'],
        "template_text": '«{{ company_name }}»\nتغییر زمان سفارش\nشماره سفارش: {{ order_id }}\nمشتری: {{ customer_name }}\nرسته: {{ service_category }}',
        "default_sms_enabled": False,
    },
    'invoice_created': {
        "event_key": 'invoice_created',
        "title": 'ایجاد فاکتور',
        "recipient_type": 'admin',
        "scope": 'company',
        "template_variables": ['company_name', 'invoice_number', 'order_id', 'customer_name'],
        "template_text": '«{{ company_name }}»\nفاکتور {{ invoice_number }} برای سفارش {{ order_id }} ایجاد شد.\nمشتری: {{ customer_name }}',
        "default_sms_enabled": False,
    },
    'invoice_issued_customer': {
        "event_key": 'invoice_issued_customer',
        "title": 'صدور فاکتور - مشتری',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'invoice_number', 'invoice_amount', 'customer_name', 'public_invoice_url'],
        "template_text": '«{{ company_name }}»\nمشتری گرامی {{ customer_name }} عزیز\nفاکتور {{ invoice_number }} به مبلغ {{ invoice_amount }} صادر شد.\nلینک مشاهده و پرداخت:\n{{ public_invoice_url }}',
        "default_sms_enabled": True,
    },
    'invoice_sent_customer': {
        "event_key": 'invoice_sent_customer',
        "title": 'ارسال فاکتور - مشتری',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'invoice_number', 'customer_name', 'public_invoice_url'],
        "template_text": '«{{ company_name }}»\nارسال فاکتور - مشتری\nشماره فاکتور: {{ invoice_number }}\nمشتری: {{ customer_name }}\nمبلغ: {{ invoice_amount }}',
        "default_sms_enabled": False,
    },
    'invoice_paid_customer': {
        "event_key": 'invoice_paid_customer',
        "title": 'پرداخت فاکتور - مشتری',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'invoice_number', 'invoice_amount', 'customer_name'],
        "template_text": '«{{ company_name }}»\nپرداخت فاکتور - مشتری\nشماره فاکتور: {{ invoice_number }}\nمشتری: {{ customer_name }}\nمبلغ: {{ invoice_amount }}',
        "default_sms_enabled": True,
    },
    'invoice_cancelled': {
        "event_key": 'invoice_cancelled',
        "title": 'لغو فاکتور',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'invoice_number', 'customer_name'],
        "template_text": '«{{ company_name }}»\nمشتری گرامی {{ customer_name }}\nفاکتور {{ invoice_number }} لغو شد.',
        "default_sms_enabled": False,
    },
    'payment_success_customer': {
        "event_key": 'payment_success_customer',
        "title": 'پرداخت موفق - مشتری',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'invoice_number', 'invoice_amount', 'customer_name'],
        "template_text": '«{{ company_name }}»\nپرداخت موفق - مشتری\nشماره فاکتور: {{ invoice_number }}\nمشتری: {{ customer_name }}\nمبلغ: {{ invoice_amount }}',
        "default_sms_enabled": True,
    },
    'payment_failed_customer': {
        "event_key": 'payment_failed_customer',
        "title": 'پرداخت ناموفق - مشتری',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'invoice_number', 'customer_name', 'public_invoice_url'],
        "template_text": '«{{ company_name }}»\nپرداخت ناموفق - مشتری\nشماره فاکتور: {{ invoice_number }}\nمشتری: {{ customer_name }}\nمبلغ: {{ invoice_amount }}',
        "default_sms_enabled": True,
    },
    'wallet_charged': {
        "event_key": 'wallet_charged',
        "title": 'شارژ کیف پول پیامک',
        "recipient_type": 'admin',
        "scope": 'platform',
        "template_variables": ['company_name', 'charged_amount', 'new_balance'],
        "template_text": '«{{ company_name }}»\nکیف پول پیامک شارژ شد.\nمبلغ شارژ: {{ charged_amount }}\nموجودی جدید: {{ new_balance }}',
        "default_sms_enabled": False,
    },
    'sms_credit_low_admin': {
        "event_key": 'sms_credit_low_admin',
        "title": 'کم بودن اعتبار پیامک',
        "recipient_type": 'admin',
        "scope": 'platform',
        "template_variables": ['company_name', 'remaining_balance'],
        "template_text": '«{{ company_name }}»\nکم بودن اعتبار پیامک\nاعتبار باقی\u200cمانده: {{ remaining_balance }}',
        "default_sms_enabled": True,
    },
    'sms_credit_empty_admin': {
        "event_key": 'sms_credit_empty_admin',
        "title": 'اتمام اعتبار پیامک',
        "recipient_type": 'admin',
        "scope": 'platform',
        "template_variables": ['company_name'],
        "template_text": '«{{ company_name }}»\nاتمام اعتبار پیامک\nاعتبار باقی\u200cمانده: {{ remaining_balance }}',
        "default_sms_enabled": True,
    },
    'sms_template_change_requested': {
        "event_key": 'sms_template_change_requested',
        "title": 'درخواست تغییر قالب پیامک',
        "recipient_type": 'platform_admin',
        "scope": 'platform',
        "template_variables": ['company_name', 'event_key', 'template_title'],
        "template_text": '«{{ company_name }}»\nدرخواست تغییر قالب پیامک\nکلید رویداد: {{ event_key }}\nعنوان قالب: {{ template_title }}',
        "default_sms_enabled": False,
    },
    'sms_template_change_approved': {
        "event_key": 'sms_template_change_approved',
        "title": 'تأیید تغییر قالب پیامک',
        "recipient_type": 'admin',
        "scope": 'platform',
        "template_variables": ['company_name', 'event_key', 'template_title'],
        "template_text": '«{{ company_name }}»\nتأیید تغییر قالب پیامک\nکلید رویداد: {{ event_key }}\nعنوان قالب: {{ template_title }}',
        "default_sms_enabled": False,
    },
    'sms_template_change_rejected': {
        "event_key": 'sms_template_change_rejected',
        "title": 'رد تغییر قالب پیامک',
        "recipient_type": 'admin',
        "scope": 'platform',
        "template_variables": ['company_name', 'event_key', 'template_title', 'reject_reason'],
        "template_text": '«{{ company_name }}»\nرد تغییر قالب پیامک\nکلید رویداد: {{ event_key }}\nعنوان قالب: {{ template_title }}',
        "default_sms_enabled": False,
    },
    'sms_outbox_failed': {
        "event_key": 'sms_outbox_failed',
        "title": 'خطا در ارسال پیامک',
        "recipient_type": 'admin',
        "scope": 'platform',
        "template_variables": ['company_name', 'phone_number', 'error_message'],
        "template_text": '«{{ company_name }}»\nخطا در ارسال پیامک',
        "default_sms_enabled": False,
    },
    'subscription_expiring_admin': {
        "event_key": 'subscription_expiring_admin',
        "title": 'نزدیک شدن پایان اشتراک',
        "recipient_type": 'admin',
        "scope": 'platform',
        "template_variables": ['company_name', 'expiry_date', 'days_remaining'],
        "template_text": '«{{ company_name }}»\nنزدیک شدن پایان اشتراک\nتاریخ پایان: {{ expiry_date }}\nروزهای باقی\u200cمانده: {{ days_remaining }}',
        "default_sms_enabled": True,
    },
    'subscription_expired_admin': {
        "event_key": 'subscription_expired_admin',
        "title": 'پایان اشتراک',
        "recipient_type": 'admin',
        "scope": 'platform',
        "template_variables": ['company_name'],
        "template_text": '«{{ company_name }}»\nپایان اشتراک\nتاریخ پایان: {{ expiry_date }}\nروزهای باقی\u200cمانده: {{ days_remaining }}',
        "default_sms_enabled": True,
    },
    'platform_payment_success_admin': {
        "event_key": 'platform_payment_success_admin',
        "title": 'پرداخت موفق پلتفرمی',
        "recipient_type": 'admin',
        "scope": 'platform',
        "template_variables": ['company_name', 'amount', 'invoice_number'],
        "template_text": '«{{ company_name }}»\nپرداخت پلتفرمی شما با موفقیت ثبت شد.\nمبلغ: {{ amount }}\nشماره فاکتور: {{ invoice_number }}',
        "default_sms_enabled": True,
    },
    'survey_request_customer': {
        "event_key": 'survey_request_customer',
        "title": 'نظرسنجی - مشتری',
        "recipient_type": 'customer',
        "scope": 'company',
        "template_variables": ['company_name', 'order_id', 'customer_name'],
        "template_text": '«{{ company_name }}»\nنظرسنجی - مشتری',
        "default_sms_enabled": False,
    },
}


def get_default_template_map() -> dict[str, dict]:
    return dict(SMS_DEFAULT_TEMPLATES)


def get_default_templates() -> list[dict]:
    return [SMS_DEFAULT_TEMPLATES[key] for key in SMS_DEFAULT_TEMPLATES]


def get_default_template(event_key: str) -> dict | None:
    return SMS_DEFAULT_TEMPLATES.get(str(event_key or "").strip())


def get_sms_supported_template_keys() -> list[str]:
    return list(SMS_DEFAULT_TEMPLATES.keys())


def validate_default_templates() -> list[str]:
    errors: list[str] = []
    supported = set(get_sms_supported_event_keys())
    defined = set(SMS_DEFAULT_TEMPLATES.keys())
    missing = sorted(supported - defined)
    extra = sorted(defined - supported)
    if missing:
        errors.append(f"Missing SMS default templates: {missing}")
    if extra:
        errors.append(f"Templates defined for non-SMS events: {extra}")
    for key, item in SMS_DEFAULT_TEMPLATES.items():
        if not (item.get("template_text") or "").strip():
            errors.append(f"Empty template_text for {key}")
        definition = EVENT_DEFINITIONS.get(key)
        if definition is None:
            continue
        declared = set(definition.template_variables)
        for var in item.get("template_variables", []):
            if var not in declared:
                errors.append(f"{key}: variable {var!r} not declared in event catalog")
    return errors
