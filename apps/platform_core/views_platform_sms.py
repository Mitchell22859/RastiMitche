"""Platform owner SMS views."""
from datetime import time

from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import require_platform_owner

from .models import PlatformSMSMessageTypeSetting, PlatformSMSOutbox, PlatformSMSProviderSetting
from .services_platform_sms import (
    PlatformSMSMessageTypeService,
    PlatformSMSOutboxProcessorService,
    PlatformSMSProviderService,
    PlatformSMSSendService,
)


def _parse_time(raw: str):
    raw = (raw or "").strip()
    if not raw:
        return None
    parts = raw.split(":")
    if len(parts) < 2:
        raise ValueError("ساعت باید با فرمت HH:MM باشد.")
    return time(hour=int(parts[0]), minute=int(parts[1]))


@require_platform_owner
def platform_sms_index(request: HttpRequest) -> HttpResponse:
    PlatformSMSMessageTypeService.ensure_defaults()
    queued = PlatformSMSOutbox.objects.filter(status=PlatformSMSOutbox.Status.QUEUED).count()
    failed = PlatformSMSOutbox.objects.filter(status=PlatformSMSOutbox.Status.FAILED).count()
    sent = PlatformSMSOutbox.objects.filter(status=PlatformSMSOutbox.Status.SENT).count()
    provider = PlatformSMSProviderService.get_or_create_singleton()
    return render(request, "platform_core/platform_sms/index.html", {"queued": queued, "failed": failed, "sent": sent, "provider": provider})


@require_platform_owner
def platform_sms_message_types(request: HttpRequest) -> HttpResponse:
    settings = PlatformSMSMessageTypeService.ensure_defaults()
    success = ""
    error = ""
    if request.method == "POST":
        try:
            if request.POST.get("action") == "apply_company_defaults":
                count = PlatformSMSMessageTypeService.apply_company_sms_defaults()
                success = f"پیش‌فرض پیامک برای {count} تنظیم شرکت اعمال شد."
            else:
                for row in settings:
                    key = row.key
                    row.is_active = bool(request.POST.get(f"is_active_{key}"))
                    row.default_company_sms_enabled = bool(request.POST.get(f"default_sms_{key}"))
                    row.send_start_time = _parse_time(request.POST.get(f"start_{key}", ""))
                    row.send_end_time = _parse_time(request.POST.get(f"end_{key}", ""))
                    row.updated_by = request.user
                    row.save(update_fields=["is_active", "default_company_sms_enabled", "send_start_time", "send_end_time", "updated_by", "updated_at"])
                success = "تنظیمات نوع پیامک ذخیره شد."
        except Exception as exc:
            error = str(exc)
        settings = PlatformSMSMessageTypeService.ensure_defaults()
    return render(request, "platform_core/platform_sms/message_types.html", {"settings": settings, "success": success, "error": error, "payer_company": PlatformSMSMessageTypeSetting.Payer.COMPANY})


@require_platform_owner
def platform_sms_provider_settings(request: HttpRequest) -> HttpResponse:
    provider = PlatformSMSProviderService.get_or_create_singleton()
    success = ""
    error = ""
    if request.method == "POST":
        try:
            provider.name = request.POST.get("name", "").strip() or provider.name
            provider.provider_type = request.POST.get("provider_type", provider.provider_type)
            provider.api_key = request.POST.get("api_key", "").strip()
            provider.sender_number = request.POST.get("sender_number", "").strip()
            provider.is_active = bool(request.POST.get("is_active"))
            provider.updated_by = request.user
            provider.save()
            success = "تنظیمات ارائه‌دهنده پیامک پلتفرم ذخیره شد."
        except Exception as exc:
            error = str(exc)
    return render(request, "platform_core/platform_sms/provider.html", {"provider": provider, "provider_choices": PlatformSMSProviderSetting.ProviderType.choices, "success": success, "error": error})


@require_platform_owner
def platform_sms_outbox(request: HttpRequest) -> HttpResponse:
    import re as _re
    status = (request.GET.get("status") or "").strip()
    messages = list(PlatformSMSOutbox.objects.select_related("recipient_company", "provider").order_by("-created_at")[:200])
    if status:
        messages = [m for m in messages if m.status == status]
    for m in messages:
        if "password_reset" in (m.template_key or ""):
            m.display_message = _re.sub(r"\b\d{6}\b", "******", m.message or "")
        else:
            m.display_message = (m.message or "")
    return render(request, "platform_core/platform_sms/outbox.html", {"messages": messages, "status": status, "status_choices": PlatformSMSOutbox.Status.choices})




@require_platform_owner
def platform_sms_outbox_detail(request: HttpRequest, sms_id: int) -> HttpResponse:
    sms = get_object_or_404(PlatformSMSOutbox.objects.select_related('recipient_company', 'provider'), id=sms_id)
    return render(request, 'platform_core/platform_sms/detail.html', {'sms': sms})
@require_platform_owner
def platform_sms_outbox_send_now(request: HttpRequest, sms_id: int) -> HttpResponse:
    sms = get_object_or_404(PlatformSMSOutbox, id=sms_id)
    if request.method == "POST":
        PlatformSMSSendService.send(sms=sms)
    return redirect("/owner-platform/platform-sms/outbox/")


@require_platform_owner
def platform_sms_process_outbox(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        PlatformSMSOutboxProcessorService.process(limit=50, dry_run=False)
    return redirect("/owner-platform/platform-sms/outbox/")
