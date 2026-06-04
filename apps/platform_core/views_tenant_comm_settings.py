"""
Tenant communication settings.

Company admins can enable/disable company-paid notification/SMS events here.
Phase 19B: Template view, preview, and change request views.
"""
from __future__ import annotations

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.template import Context, Template

from apps.accounts.permissions import require_tenant_role
from apps.notifications.event_catalog import EVENT_DEFINITIONS, Payer
from apps.notifications.models import NotificationSetting
from apps.notifications.services import NotificationSettingService
from apps.sms.models import SMSTemplate
from apps.sms.models_master import SMSMasterTemplate, SMSTemplateChangeRequest


RECIPIENT_LABELS = {
    "CUSTOMER": "مشتری",
    "TECHNICIAN": "نیروی خدماتی",
    "COMPANY_ADMIN": "مدیر شرکت",
    "AVAILABLE_TECHNICIANS": "نیروهای واجد شرایط",
}

SAMPLE_PREVIEW_CONTEXT = {
    "company_name": "شرکت نمونه",
    "customer_name": "علی رضایی",
    "customer_phone": "09121234567",
    "customer_address": "تهران، خیابان نمونه، پلاک ۱۰",
    "technician_name": "رضا محمدی",
    "technician_phone": "09129876543",
    "order_id": "123",
    "order_title": "سفارش نمونه",
    "service_category": "نظافت منزل",
    "invoice_number": "INV-123",
    "invoice_amount": "۲,۵۰۰,۰۰۰",
    "public_invoice_link": "https://example.com/i/sample",
    "survey_link": "https://example.com/survey/sample",
    "reason": "نمونه علت",
    "admin_name": "مدیر نمونه",
    "admin_phone": "09120000000",
    "support_phone": "02191001234",
    "subscription_plan": "پلن حرفه‌ای",
    "subscription_end_date": "1404/06/31",
    "platform_invoice_number": "PB-001",
    "platform_invoice_amount": "۵۰۰,۰۰۰",
    "payment_link": "https://example.com/pay/sample",
}


def _get_or_create_notification_setting(company, event_key, definition):
    setting, _ = NotificationSetting.objects.get_or_create(
        company=company,
        event_key=event_key,
        defaults={
            "sms_enabled": bool(definition.default_sms_enabled),
            "in_app_enabled": bool(definition.default_in_app_enabled),
        },
    )
    return setting


def _get_effective_template(company, event_key):
    """Use centralized resolver for consistency between display and sending."""
    from apps.sms.template_resolver import resolve_effective_sms_template
    return resolve_effective_sms_template(company=company, event_key=event_key)


def _render_preview(template_text):
    """Render template text with sample Persian context for preview."""
    if not template_text:
        return ""
    try:
        tpl = Template(template_text)
        ctx = Context(SAMPLE_PREVIEW_CONTEXT)
        return tpl.render(ctx)
    except Exception:
        return "(خطا در رندر پیش‌نمایش)"


def _build_event_rows(company):
    NotificationSettingService.ensure_defaults(company=company)

    settings_map = {
        item.event_key: item
        for item in NotificationSetting.objects.filter(company=company)
    }

    # Pre-fetch company templates and master templates for has_template check
    company_template_keys = set(
        SMSTemplate.objects.filter(company=company).values_list("key", flat=True)
    )
    master_template_keys = set(
        SMSMasterTemplate.objects.values_list("key", flat=True)
    )

    rows = []
    for event_key, definition in EVENT_DEFINITIONS.items():
        # Tenant admins manage only company-paid events.
        # Platform-paid alerts are managed by platform owner.
        if definition.payer != Payer.COMPANY:
            continue

        setting = settings_map.get(event_key)
        if setting is None:
            setting = _get_or_create_notification_setting(company, event_key, definition)

        has_template = (event_key in company_template_keys) or (event_key in master_template_keys)

        rows.append({
            "event_key": event_key,
            "title": definition.title,
            "recipient": RECIPIENT_LABELS.get(definition.recipient, definition.recipient),
            "sms_enabled": bool(getattr(setting, "sms_enabled", False)),
            "in_app_enabled": bool(getattr(setting, "in_app_enabled", False)),
            "default_sms_enabled": bool(definition.default_sms_enabled),
            "default_in_app_enabled": bool(definition.default_in_app_enabled),
            "has_template": has_template,
        })

    return rows


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_comm_settings(request: HttpRequest, **kwargs) -> HttpResponse:
    """GET: show company communication settings. POST: toggle event settings."""
    company = request.company
    success = ""
    error = ""

    if request.method == "POST":
        event_key = request.POST.get("event_key", "").strip()
        field = request.POST.get("field", "").strip()
        value = request.POST.get("value", "").strip() == "1"

        definition = EVENT_DEFINITIONS.get(event_key)
        if not definition or definition.payer != Payer.COMPANY:
            error = "این رویداد برای تنظیمات شرکت معتبر نیست."
        elif field not in ("sms_enabled", "in_app_enabled"):
            error = "نوع تنظیم معتبر نیست."
        else:
            setting = _get_or_create_notification_setting(company, event_key, definition)
            setattr(setting, field, value)
            setting.save(update_fields=[field, "updated_at"])
            success = "تنظیمات پیام ذخیره شد."

    event_rows = _build_event_rows(company)

    return render(request, "tenants/admin_comm_settings.html", {
        "company": company,
        "company_code": company.code,
        "current_path": request.path,
        "success": success,
        "error": error,
        "event_rows": event_rows,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_sms_template_view(request: HttpRequest, event_key: str, **kwargs) -> HttpResponse:
    """
    View the effective SMS template for a given event key (readonly).
    Shows template text, source, allowed variables, and a rendered preview.
    """
    company = request.company

    # Validate event_key
    definition = EVENT_DEFINITIONS.get(event_key)
    if not definition or definition.payer != Payer.COMPANY:
        return render(request, "tenants/admin_sms_template_view.html", {
            "company": company,
            "company_code": company.code,
            "error": "رویداد معتبر نیست.",
            "event_key": event_key,
            "event_title": "",
            "template_text": None,
            "template_source": None,
            "allowed_variables": "",
            "preview": "",
        })

    effective = _get_effective_template(company, event_key)
    template_text = effective["text"] if effective else None
    source = effective["source"] if effective else None
    source_label = effective["source_label"] if effective else ""
    allowed_variables = effective["allowed_variables"] if effective else ""
    preview = _render_preview(template_text) if template_text else ""

    return render(request, "tenants/admin_sms_template_view.html", {
        "company": company,
        "company_code": company.code,
        "event_key": event_key,
        "event_title": definition.title,
        "template_text": template_text,
        "template_source": source,
        "template_source_label": source_label,
        "allowed_variables": allowed_variables,
        "preview": preview,
        "error": "",
    })


@require_tenant_role("COMPANY_ADMIN")
def tenant_sms_template_change_request(request: HttpRequest, event_key: str, **kwargs) -> HttpResponse:
    """
    Form to submit a change request for an SMS template.
    Only company admins can submit change requests.
    """
    company = request.company
    success = ""
    error = ""

    # Validate event_key
    definition = EVENT_DEFINITIONS.get(event_key)
    if not definition or definition.payer != Payer.COMPANY:
        return render(request, "tenants/admin_sms_template_request.html", {
            "company": company,
            "company_code": company.code,
            "error": "رویداد معتبر نیست.",
            "event_key": event_key,
            "event_title": "",
            "current_template_text": "",
            "tone_choices": SMSTemplateChangeRequest.Tone.choices,
            "success": "",
        })

    effective = _get_effective_template(company, event_key)
    template_text = effective["text"] if effective else None

    if request.method == "POST":
        requested_text = request.POST.get("requested_template_text", "").strip()
        requested_tone = request.POST.get("requested_tone", "custom").strip()
        note = request.POST.get("note", "").strip()

        if not requested_text:
            error = "لطفاً متن پیشنهادی قالب را وارد کنید."
        else:
            SMSTemplateChangeRequest.objects.create(
                company=company,
                event_key=event_key,
                current_template_text=template_text or "",
                requested_template_text=requested_text,
                requested_tone=requested_tone,
                note=note,
                created_by=request.user,
            )
            success = "درخواست تغییر قالب با موفقیت ارسال شد. تیم پلتفرم بررسی خواهد کرد."

    return render(request, "tenants/admin_sms_template_request.html", {
        "company": company,
        "company_code": company.code,
        "event_key": event_key,
        "event_title": definition.title,
        "current_template_text": template_text or "",
        "tone_choices": SMSTemplateChangeRequest.Tone.choices,
        "success": success,
        "error": error,
    })
