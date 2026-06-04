"""
Management command: seed default communication templates.

Usage:
    python manage.py seed_communication_templates

Creates or updates global default CommunicationTemplate rows.
- Uses company=None for global defaults
- Idempotent: running multiple times does not create duplicates
- Uses event_key + channel + recipient_type + company=None as unique identity
- Does not create company-specific templates
- Does not send SMS or call external APIs

These are formal Persian templates used as system defaults.
Platform Owner can edit them later or create company-specific overrides.
"""
from django.core.management.base import BaseCommand

from apps.platform_core.models import CommunicationTemplate


# Default template definitions
DEFAULT_TEMPLATES = [
    {
        "event_key": "ORDER_CREATED",
        "channel": "SMS",
        "recipient_type": "COMPANY_ADMIN",
        "title_template": "ثبت سفارش جدید",
        "body_template": (
            "شرکت {{ company_name }}\n"
            "یک سفارش جدید با کد {{ order_id }} ثبت شد.\n"
            "نام مشتری: {{ customer_name }}\n"
            "آدرس: {{ customer_address }}\n"
            "کد پیگیری: {{ tracking_code }}"
        ),
        "action_label": "مشاهده سفارش",
        "action_url_template": "/{{ company_code }}/admin/orders/{{ order_id }}/",
        "is_required": False,
        "allow_company_toggle": True,
    },
    {
        "event_key": "ORDER_ASSIGNED",
        "channel": "SMS",
        "recipient_type": "TECHNICIAN",
        "title_template": "ارجاع سفارش",
        "body_template": (
            "تکنسین گرامی {{ technician_name }}\n"
            "یک سفارش از طرف شرکت {{ company_name }} به شما ارجاع شد.\n"
            "کد سفارش: {{ order_id }}\n"
            "نام مشتری: {{ customer_name }}\n"
            "آدرس: {{ customer_address }}\n"
            "وضعیت: {{ order_status }}"
        ),
        "action_label": "مشاهده سفارش",
        "action_url_template": "/{{ company_code }}/tech/orders/{{ order_id }}/",
        "is_required": False,
        "allow_company_toggle": True,
    },
    {
        "event_key": "ORDER_STATUS_CHANGED",
        "channel": "SMS",
        "recipient_type": "COMPANY_ADMIN",
        "title_template": "تغییر وضعیت سفارش",
        "body_template": (
            "شرکت {{ company_name }}\n"
            "وضعیت سفارش {{ order_id }} تغییر کرد.\n"
            "وضعیت جدید: {{ order_status }}\n"
            "کد پیگیری: {{ tracking_code }}"
        ),
        "action_label": "مشاهده سفارش",
        "action_url_template": "/{{ company_code }}/admin/orders/{{ order_id }}/",
        "is_required": False,
        "allow_company_toggle": True,
    },
    {
        "event_key": "INVOICE_CREATED",
        "channel": "SMS",
        "recipient_type": "COMPANY_ADMIN",
        "title_template": "صدور فاکتور",
        "body_template": (
            "شرکت {{ company_name }}\n"
            "برای سفارش {{ order_id }} فاکتور صادر شد.\n"
            "شماره فاکتور: {{ invoice_id }}\n"
            "مبلغ فاکتور: {{ invoice_amount }} ریال"
        ),
        "action_label": "مشاهده فاکتور",
        "action_url_template": "/{{ company_code }}/admin/invoices/{{ invoice_id }}/",
        "is_required": False,
        "allow_company_toggle": True,
    },
    {
        "event_key": "PAYMENT_RECEIVED",
        "channel": "SMS",
        "recipient_type": "COMPANY_ADMIN",
        "title_template": "ثبت پرداخت",
        "body_template": (
            "شرکت {{ company_name }}\n"
            "پرداخت مربوط به فاکتور {{ invoice_id }} با موفقیت ثبت شد.\n"
            "مبلغ: {{ invoice_amount }} ریال\n"
            "وضعیت پرداخت: {{ payment_status }}"
        ),
        "action_label": "مشاهده فاکتور",
        "action_url_template": "/{{ company_code }}/admin/invoices/{{ invoice_id }}/",
        "is_required": False,
        "allow_company_toggle": True,
    },
    {
        "event_key": "SMS_CREDIT_LOW",
        "channel": "INTERNAL_NOTIFICATION",
        "recipient_type": "COMPANY_ADMIN",
        "title_template": "هشدار کاهش اعتبار پیامک",
        "body_template": (
            "شرکت {{ company_name }}\n"
            "اعتبار پیامک شما رو به اتمام است.\n"
            "اعتبار فعلی: {{ sms_balance }} ریال\n"
            "تعداد پیامک قابل ارسال: {{ sms_remaining_count }}"
        ),
        "action_label": "شارژ پیامک",
        "action_url_template": "/{{ company_code }}/admin/sms-credit/",
        "is_required": True,
        "allow_company_toggle": False,
    },
    {
        "event_key": "SMS_CREDIT_EMPTY",
        "channel": "INTERNAL_NOTIFICATION",
        "recipient_type": "COMPANY_ADMIN",
        "title_template": "اتمام اعتبار پیامک",
        "body_template": (
            "شرکت {{ company_name }}\n"
            "اعتبار پیامک شما به پایان رسیده است.\n"
            "تا زمان شارژ مجدد، ارسال پیامک متوقف خواهد شد."
        ),
        "action_label": "شارژ مجدد",
        "action_url_template": "/{{ company_code }}/admin/sms-credit/recharge/",
        "is_required": True,
        "allow_company_toggle": False,
    },
    {
        "event_key": "COMPANY_APPROVED",
        "channel": "INTERNAL_NOTIFICATION",
        "recipient_type": "COMPANY_ADMIN",
        "title_template": "فعال‌سازی پنل شرکت",
        "body_template": (
            "شرکت {{ company_name }} با موفقیت توسط مالک پلتفرم تأیید و فعال شد.\n"
            "اکنون می‌توانید وارد پنل مدیریت شرکت شوید."
        ),
        "action_label": "ورود به پنل",
        "action_url_template": "/{{ company_code }}/admin/",
        "is_required": True,
        "allow_company_toggle": False,
    },
    {
        "event_key": "TECHNICIAN_NOTIFICATION",
        "channel": "INTERNAL_NOTIFICATION",
        "recipient_type": "TECHNICIAN",
        "title_template": "اعلان تکنسین",
        "body_template": (
            "تکنسین گرامی {{ technician_name }}\n"
            "یک اعلان جدید از طرف شرکت {{ company_name }} برای شما ثبت شده است.\n"
            "کد سفارش: {{ order_id }}"
        ),
        "action_label": "مشاهده",
        "action_url_template": "/{{ company_code }}/tech/orders/{{ order_id }}/",
        "is_required": False,
        "allow_company_toggle": True,
    },
    {
        "event_key": "OPERATOR_NOTIFICATION",
        "channel": "INTERNAL_NOTIFICATION",
        "recipient_type": "OPERATOR",
        "title_template": "اعلان اپراتور",
        "body_template": (
            "اپراتور گرامی\n"
            "یک اعلان جدید برای شرکت {{ company_name }} ثبت شده است.\n"
            "کد سفارش: {{ order_id }}"
        ),
        "action_label": "مشاهده سفارش",
        "action_url_template": "/{{ company_code }}/admin/orders/{{ order_id }}/",
        "is_required": False,
        "allow_company_toggle": True,
    },
]


class Command(BaseCommand):
    help = "Seed default global communication templates (idempotent)."

    def handle(self, *args, **options):
        created_count = 0
        updated_count = 0

        for tpl_data in DEFAULT_TEMPLATES:
            # Unique identity: event_key + channel + recipient_type + company=None
            lookup = {
                "event_key": tpl_data["event_key"],
                "channel": tpl_data["channel"],
                "recipient_type": tpl_data["recipient_type"],
                "company": None,
            }
            defaults = {
                "title_template": tpl_data["title_template"],
                "body_template": tpl_data["body_template"],
                "action_label": tpl_data.get("action_label", ""),
                "action_url_template": tpl_data.get("action_url_template", ""),
                "is_active": True,
                "is_required": tpl_data.get("is_required", False),
                "allow_company_toggle": tpl_data.get("allow_company_toggle", True),
            }

            obj, created = CommunicationTemplate.objects.update_or_create(
                **lookup, defaults=defaults
            )

            if created:
                created_count += 1
                self.stdout.write(f"  Created: {tpl_data['event_key']} / {tpl_data['channel']} / {tpl_data['recipient_type']}")
            else:
                updated_count += 1
                self.stdout.write(f"  Updated: {tpl_data['event_key']} / {tpl_data['channel']} / {tpl_data['recipient_type']}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Done! {created_count} created, {updated_count} updated. "
            f"Total: {len(DEFAULT_TEMPLATES)} global default templates."
        ))
