"""
SMS - Views.

Admin views for SMS outbox and template management.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import require_tenant_role

from .models import SMSTemplate
from .selectors import SMSOutboxSelector


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_outbox_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """Admin view of SMS outbox for the company."""
    company = request.company
    messages = SMSOutboxSelector.get_for_company(company=company)
    return render(request, "sms/outbox_list.html", {
        "messages": messages,
        "company": company,
    })


def _sync_templates_from_notification_settings(*, company) -> None:
    try:
        from apps.notifications.models import NotificationSetting
        from apps.notifications.services import NotificationSettingService
    except Exception:
        return

    NotificationSettingService.ensure_defaults(company=company)
    settings_by_key = {
        row.event_key: row
        for row in NotificationSetting.objects.filter(company=company)
    }

    for template in SMSTemplate.objects.filter(company=company):
        setting = settings_by_key.get(template.key)
        if setting is None:
            continue
        if template.is_active != setting.sms_enabled:
            template.is_active = setting.sms_enabled
            template.save(update_fields=["is_active", "updated_at"])


def _sync_notification_setting_from_template(*, template: SMSTemplate) -> None:
    try:
        from apps.notifications.models import NotificationSetting
        from apps.notifications.services import NotificationSettingService
    except Exception:
        return

    NotificationSettingService.ensure_defaults(company=template.company)
    setting = NotificationSetting.objects.filter(
        company=template.company,
        event_key=template.key,
    ).first()
    if setting is None:
        return

    if setting.sms_enabled != template.is_active:
        setting.sms_enabled = template.is_active
        setting.save(update_fields=["sms_enabled", "updated_at"])


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_template_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """Redirect to communication settings — direct template management removed."""
    company = request.company
    from django.contrib import messages
    messages.info(request, "مدیریت قالب‌های پیامک از بخش تنظیمات ارتباطات انجام می‌شود.")
    return redirect(f"/{company.code}/admin/communication-settings/")


@require_tenant_role("COMPANY_ADMIN")
def sms_template_create(request: HttpRequest, **kwargs) -> HttpResponse:
    """Redirect — direct template creation removed."""
    company = request.company
    return redirect(f"/{company.code}/admin/communication-settings/")


@require_tenant_role("COMPANY_ADMIN")
def sms_template_edit(request: HttpRequest, pk: int, **kwargs) -> HttpResponse:
    company = request.company
    template = get_object_or_404(SMSTemplate, pk=pk, company=company)
    # Phase 19B: Redirect direct editing to the governance template view page
    return redirect(f"/{company.code}/admin/communication-settings/template/{template.key}/")


@require_tenant_role("COMPANY_ADMIN")
def sms_template_toggle(request: HttpRequest, pk: int, **kwargs) -> HttpResponse:
    company = request.company
    template = get_object_or_404(SMSTemplate, pk=pk, company=company)
    template.is_active = not template.is_active
    template.save(update_fields=["is_active", "updated_at"])
    _sync_notification_setting_from_template(template=template)
    return redirect(f"/{company.code}/admin/sms/templates/")



# =============================================================================
# SMS OUTBOX ADMIN (Phase 26B + 26C)
# =============================================================================

PAGE_SIZE = 50


def _build_filter_query_string(*, status_filter: str, template_key_filter: str, search_q: str) -> str:
    """Build query string from active filters (for pagination links)."""
    from urllib.parse import urlencode
    params = {}
    if status_filter:
        params["status"] = status_filter
    if template_key_filter:
        params["template_key"] = template_key_filter
    if search_q:
        params["q"] = search_q
    return urlencode(params)


def _sms_outbox_cost_context(*, company):
    """Return pricing/provider/wallet summary for SMS outbox UI."""
    try:
        from apps.platform_core.services_sms_credit import SMSCreditService
        from .services import SMSSendingSafetyService
    except Exception as exc:
        return {
            "available": False,
            "error": str(exc),
            "wallet_balance_rial": 0,
            "price_per_sms_rial": 0,
            "characters_per_sms": 0,
            "provider_enabled": False,
            "provider_label": "-",
            "provider_reason": "اطلاعات هزینه پیامک در دسترس نیست.",
        }

    pricing = SMSCreditService.get_pricing()
    wallet = SMSCreditService.get_or_create_wallet(company)
    provider_status = SMSSendingSafetyService.get_status(company=company)
    provider = provider_status.get("provider")

    return {
        "available": True,
        "error": "",
        "wallet_balance_rial": int(getattr(wallet, "balance_rial", 0) or 0),
        "price_per_sms_rial": int(getattr(pricing, "price_per_sms_rial", 0) or 0),
        "characters_per_sms": int(getattr(pricing, "characters_per_sms", 0) or 0),
        "provider_enabled": bool(provider_status.get("enabled")),
        "provider_label": str(provider) if provider else "-",
        "provider_reason": provider_status.get("reason") or "",
    }


def _estimate_sms_cost(*, message: str, cost_context: dict) -> dict:
    """Estimate cost using the current owner pricing.

    This is the correct display mode for queued SMS rows because they have not
    been sent yet. If owner pricing changes before sending, queued rows must be
    priced with the new values at send time.
    """
    import math

    text = message or ""
    length = len(text)
    chars_per_sms = int(cost_context.get("characters_per_sms") or 0)
    price_per_sms = int(cost_context.get("price_per_sms_rial") or 0)

    if length <= 0 or chars_per_sms <= 0:
        parts = 0
    else:
        parts = int(math.ceil(length / chars_per_sms))

    cost = int(parts * price_per_sms)
    return {
        "length": length,
        "parts": parts,
        "cost_rial": cost,
        "characters_per_sms": chars_per_sms,
        "price_per_sms_rial": price_per_sms,
        "is_snapshot": False,
        "is_final": False,
        "pricing_snapshot_at": None,
        "cost_label": "هزینه تخمینی",
        "pricing_basis_label": "تعرفه فعلی",
    }


def _sms_cost_snapshot_for_ui(*, sms, cost_context: dict) -> dict:
    """Return SMS pricing values for UI.

    Business rule:
    - queued/sending rows show an estimate using current owner pricing.
    - sent/delivered/failed rows show the fixed snapshot captured at the real
      send attempt.

    Old queue-time snapshots may exist from a previous patch. They are ignored
    while the row is still queued so stale pricing does not affect display or
    future sending.
    """
    status = getattr(sms, "status", "") or ""
    length = int(getattr(sms, "message_length_snapshot", 0) or 0)
    parts = int(getattr(sms, "sms_parts_snapshot", 0) or 0)
    cost = int(getattr(sms, "sms_cost_rial_snapshot", 0) or 0)
    chars_per_sms = int(getattr(sms, "pricing_characters_per_sms_snapshot", 0) or 0)
    price_per_sms = int(getattr(sms, "pricing_price_per_sms_rial_snapshot", 0) or 0)
    snapshot_at = getattr(sms, "pricing_snapshot_at", None)
    has_snapshot = bool(snapshot_at) or any([length, parts, cost, chars_per_sms, price_per_sms])

    if status in ("sent", "delivered", "failed", "cancelled") and has_snapshot:
        return {
            "length": length,
            "parts": parts,
            "cost_rial": cost,
            "characters_per_sms": chars_per_sms,
            "price_per_sms_rial": price_per_sms,
            "is_snapshot": True,
            "is_final": True,
            "pricing_snapshot_at": snapshot_at,
            "cost_label": "هزینه ثبت‌شده",
            "pricing_basis_label": "تعرفه زمان تلاش ارسال",
        }

    return _estimate_sms_cost(message=getattr(sms, "message", "") or "", cost_context=cost_context)


def _attach_sms_outbox_ui_info(*, sms_list, company) -> dict:
    """
    Attach calculated UI-only fields to SMSOutbox objects.

    No database field is changed here. This is only for showing summary info in
    /<company>/admin/sms/outbox/ and the detail page.
    """
    cost_context = _sms_outbox_cost_context(company=company)
    wallet_balance = int(cost_context.get("wallet_balance_rial") or 0)
    provider_enabled = bool(cost_context.get("provider_enabled"))
    provider_reason = cost_context.get("provider_reason") or ""

    for sms in sms_list:
        estimate = _sms_cost_snapshot_for_ui(sms=sms, cost_context=cost_context)
        sms.ui_message_length = estimate["length"]
        sms.ui_sms_parts = estimate["parts"]
        sms.ui_sms_cost_rial = estimate["cost_rial"]
        sms.ui_wallet_balance_rial = wallet_balance
        sms.ui_price_per_sms_rial = estimate["price_per_sms_rial"]
        sms.ui_characters_per_sms = estimate["characters_per_sms"]
        sms.ui_pricing_is_snapshot = estimate.get("is_snapshot", False)
        sms.ui_pricing_is_final = estimate.get("is_final", False)
        sms.ui_pricing_snapshot_at = estimate.get("pricing_snapshot_at")
        sms.ui_cost_label = estimate.get("cost_label") or "هزینه"
        sms.ui_pricing_basis_label = estimate.get("pricing_basis_label") or "تعرفه"
        sms.ui_provider_enabled = provider_enabled
        sms.ui_provider_label = cost_context.get("provider_label") or "-"
        if getattr(sms, "template_key", "") == "discount_code_customer":
            try:
                from apps.reports.discount_services import mask_discount_sms_text
                sms.ui_display_message = mask_discount_sms_text(getattr(sms, "message", "") or "")
            except Exception:
                sms.ui_display_message = "پیامک تخفیف محرمانه برای مشتری ارسال شد."
            sms.ui_template_key_label = "کد تخفیف مشتری"
        else:
            sms.ui_display_message = getattr(sms, "message", "") or ""
            try:
                sms.ui_template_key_label = sms.get_template_key_display() or sms.template_key
            except Exception:
                sms.ui_template_key_label = sms.template_key


        status = getattr(sms, "status", "") or "unknown"
        error_message = getattr(sms, "error_message", "") or ""

        status_labels = {
            "queued": "در صف ارسال",
            "sending": "در حال ارسال",
            "sent": "ارسال موفق",
            "delivered": "تحویل شده",
            "failed": "ارسال ناموفق",
            "cancelled": "لغو شده",
        }
        sms.ui_delivery_status_label = status_labels.get(status, status)
        sms.ui_actual_failure_reason = error_message if status == "failed" and error_message else ""

        if status in ("sent", "delivered"):
            reason = "ارسال این پیامک با موفقیت انجام شده است."
            state = "success"
            readiness_label = "موفق"
        elif status == "failed":
            reason = error_message or "ارسال این پیامک ناموفق بوده است."
            state = "failed"
            readiness_label = "ناموفق"
        elif status == "cancelled":
            reason = error_message or "این پیامک لغو شده و برای ارسال پردازش نمی‌شود."
            state = "cancelled"
            readiness_label = "لغو شده"
        elif status == "sending":
            reason = "این پیامک در حال پردازش ارسال است."
            state = "sending"
            readiness_label = "در حال ارسال"
        elif not provider_enabled:
            reason = provider_reason or "برای این شرکت ارائه‌دهنده پیامک فعال تنظیم نشده است."
            state = "no_provider"
            readiness_label = "آماده نیست"
        elif wallet_balance < estimate["cost_rial"]:
            reason = "اگر اکنون پردازش شود، اعتبار پیامک شرکت برای ارسال این پیام کافی نیست."
            state = "insufficient_credit"
            readiness_label = "آماده نیست"
        elif status == "queued":
            reason = "در صف ارسال است و اگر پردازش شود، از نظر provider و اعتبار فعلی آماده ارسال است."
            state = "ready"
            readiness_label = "آماده ارسال"
        else:
            reason = error_message or "وضعیت ارسال برای این پیامک مشخص نیست."
            state = status or "unknown"
            readiness_label = status_labels.get(status, "نامشخص")

        sms.ui_not_send_reason = reason
        sms.ui_send_readiness = state
        sms.ui_readiness_label = readiness_label

    return cost_context


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_outbox_admin_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Admin view of SMS outbox with filtering and pagination.

    Filters:
    - status: queued, sending, sent, delivered, failed, cancelled
    - template_key: filter by template key
    - q: search by phone number

    Pagination:
    - page: page number (default 1)
    - page_size: 50 (fixed)
    """
    from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator

    from .models import SMSOutbox, SMSTemplate

    company = request.company
    status_filter = request.GET.get("status", "").strip()
    template_key_filter = request.GET.get("template_key", "").strip()
    search_q = request.GET.get("q", "").strip()

    qs = SMSOutbox.objects.filter(company=company).select_related(
        "template", "provider"
    ).order_by("-created_at")

    if status_filter:
        qs = qs.filter(status=status_filter)
    if template_key_filter:
        qs = qs.filter(template_key=template_key_filter)
    if search_q:
        qs = qs.filter(phone_number__icontains=search_q)

    paginator = Paginator(qs, PAGE_SIZE)
    page_number = request.GET.get("page", "1")
    try:
        page_obj = paginator.page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.page(1)

    outbox_cost_context = _attach_sms_outbox_ui_info(
        sms_list=page_obj.object_list,
        company=company,
    )

    filter_qs = _build_filter_query_string(
        status_filter=status_filter,
        template_key_filter=template_key_filter,
        search_q=search_q,
    )

    return render(request, "sms/outbox_admin_list.html", {
        "company": company,
        "page_obj": page_obj,
        "messages": page_obj.object_list,
        "status_filter": status_filter,
        "template_key_filter": template_key_filter,
        "search_q": search_q,
        "status_choices": SMSOutbox.Status.choices,
        "template_key_choices": SMSTemplate.TemplateKey.choices,
        "filter_qs": filter_qs,
        "outbox_cost_context": outbox_cost_context,
    })




@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_outbox_detail(request: HttpRequest, pk: int, **kwargs) -> HttpResponse:
    from .models import SMSOutbox

    company = request.company
    sms = get_object_or_404(SMSOutbox.objects.select_related('template', 'provider', 'company'), pk=pk, company=company)
    outbox_cost_context = _attach_sms_outbox_ui_info(sms_list=[sms], company=company)
    return render(request, 'sms/outbox_detail.html', {
        'company': company,
        'sms': sms,
        'display_id': f'C-{company.code.upper()}-{sms.id}',
        'outbox_cost_context': outbox_cost_context,
    })
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_outbox_send_now(request: HttpRequest, pk: int, **kwargs) -> HttpResponse:
    """
    Manual send/retry for a single SMS outbox record.

    POST-only. Only QUEUED or FAILED messages can be sent.
    SENT and DELIVERED messages are not resent.
    """
    from django.http import HttpResponseForbidden

    if request.method != "POST":
        return HttpResponseForbidden("POST only.")

    from .models import SMSOutbox
    from .services import SMSOutboxProcessorService

    company = request.company
    sms = get_object_or_404(SMSOutbox, pk=pk, company=company)

    if sms.status in (SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED):
        return redirect(f"/{company.code}/admin/sms/outbox/")

    SMSOutboxProcessorService.send_single(sms=sms)
    return redirect(f"/{company.code}/admin/sms/outbox/")


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_outbox_bulk_retry(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Bulk retry/send for multiple SMS outbox records.

    POST-only. Processes selected IDs that are QUEUED or FAILED.
    SENT and DELIVERED rows are skipped. Cross-company rows are ignored.
    """
    from django.http import HttpResponseForbidden

    if request.method != "POST":
        return HttpResponseForbidden("POST only.")

    from .models import SMSOutbox
    from .services import SMSOutboxProcessorService

    company = request.company
    selected_ids = request.POST.getlist("selected_ids")

    sent = 0
    failed = 0
    skipped = 0

    if selected_ids:
        # Only process IDs that belong to this company and are retryable
        sms_qs = SMSOutbox.objects.filter(
            pk__in=selected_ids,
            company=company,
        )
        for sms in sms_qs:
            if sms.status in (SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED):
                skipped += 1
                continue
            if sms.status in (SMSOutbox.Status.QUEUED, SMSOutbox.Status.FAILED):
                result = SMSOutboxProcessorService.send_single(sms=sms)
                if result.status in (SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED):
                    sent += 1
                else:
                    failed += 1
            else:
                skipped += 1

    # Redirect back preserving filters if present
    redirect_url = f"/{company.code}/admin/sms/outbox/"
    # Pass summary via query params (simple approach, no messages framework needed)
    from urllib.parse import urlencode
    summary_params = urlencode({
        "bulk_sent": sent,
        "bulk_failed": failed,
        "bulk_skipped": skipped,
    })
    return redirect(f"{redirect_url}?{summary_params}")



# =============================================================================
# SMS DIAGNOSTICS (Phase 26D)
# =============================================================================


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def sms_diagnostics(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    SMS provider diagnostics and safe test-send page.

    GET: Show provider info and test-send form.
    POST: Create a diagnostic outbox row and optionally send immediately.
    """
    from .services import SMSDiagnosticsService

    company = request.company
    provider_info = SMSDiagnosticsService.get_provider_info(company=company)

    result = None
    error = ""

    if request.method == "POST":
        phone_number = request.POST.get("phone_number", "").strip()
        message = request.POST.get("message", "").strip()
        send_immediately = bool(request.POST.get("send_immediately"))

        send_result = SMSDiagnosticsService.send_test(
            company=company,
            phone_number=phone_number,
            message=message,
            send_immediately=send_immediately,
        )

        if send_result["success"]:
            result = send_result["sms"]
        else:
            error = send_result["error"]

    return render(request, "sms/diagnostics.html", {
        "company": company,
        "provider_info": provider_info,
        "result": result,
        "error": error,
    })
