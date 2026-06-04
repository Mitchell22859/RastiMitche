"""
Platform Core - Communication Template Views.

DEPRECATED — This module is legacy code from a previous design iteration.

The CommunicationTemplate system is NOT connected to the active SMS/notification
dispatch pipeline. It provides a read/write UI for platform owners, but edits
have NO effect on real message delivery.

Active system (used for real SMS/notification dispatch):
    - apps.notifications.models.NotificationSetting (per-company event switches)
    - apps.notifications.models.NotificationEvent (event audit trail)
    - apps.notifications.dispatchers.NotificationDispatcher (central dispatcher)
    - apps.sms.models.SMSTemplate (per-company SMS text templates)
    - apps.sms.models.SMSOutbox (company-paid SMS queue)
    - apps.platform_core.models.PlatformSMSOutbox (platform-paid SMS queue)
    - apps.platform_core.models.PlatformSMSMessageTypeSetting (global message config)

Do NOT use CommunicationTemplate for new SMS/event work.
These views remain accessible via direct URL but are hidden from navigation.

All views require PLATFORM_OWNER role.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import require_platform_owner

from .models import CommunicationTemplate
from .services_communication import CommunicationTemplateService


@require_platform_owner
def comm_template_list(request: HttpRequest) -> HttpResponse:
    """List all communication templates with filters."""
    templates = CommunicationTemplate.objects.all()

    # Filters
    event_key = request.GET.get("event_key", "")
    channel = request.GET.get("channel", "")
    status = request.GET.get("status", "")

    if event_key:
        templates = templates.filter(event_key=event_key)
    if channel:
        templates = templates.filter(channel=channel)
    if status == "active":
        templates = templates.filter(is_active=True)
    elif status == "inactive":
        templates = templates.filter(is_active=False)

    return render(request, "platform_core/comm_templates/list.html", {
        "templates": templates,
        "event_key_choices": CommunicationTemplate.EventKey.choices,
        "channel_choices": CommunicationTemplate.Channel.choices,
        "filter_event_key": event_key,
        "filter_channel": channel,
        "filter_status": status,
    })


@require_platform_owner
def comm_template_create(request: HttpRequest) -> HttpResponse:
    """GET: show form. POST: create template."""
    errors = {}

    if request.method == "POST":
        event_key = request.POST.get("event_key", "")
        channel = request.POST.get("channel", "")
        recipient_type = request.POST.get("recipient_type", "")
        title_template = request.POST.get("title_template", "").strip()
        body_template = request.POST.get("body_template", "").strip()
        action_label = request.POST.get("action_label", "").strip()
        action_url_template = request.POST.get("action_url_template", "").strip()
        is_active = request.POST.get("is_active") == "on"
        is_required = request.POST.get("is_required") == "on"
        allow_company_toggle = request.POST.get("allow_company_toggle") == "on"

        # Validation
        if not event_key:
            errors["event_key"] = "رویداد الزامی است."
        if not channel:
            errors["channel"] = "کانال الزامی است."
        if not recipient_type:
            errors["recipient_type"] = "نوع گیرنده الزامی است."
        if not title_template:
            errors["title_template"] = "عنوان الزامی است."
        if not body_template:
            errors["body_template"] = "متن پیام الزامی است."

        # Validate placeholders
        if title_template:
            valid, invalid = CommunicationTemplateService.validate_placeholders(title_template)
            if not valid:
                errors["title_template"] = f"متغیرهای نامعتبر: {', '.join(invalid)}"
        if body_template:
            valid, invalid = CommunicationTemplateService.validate_placeholders(body_template)
            if not valid:
                errors["body_template"] = f"متغیرهای نامعتبر: {', '.join(invalid)}"

        # Validate URL
        if action_url_template and not CommunicationTemplateService.validate_action_url(action_url_template):
            errors["action_url_template"] = "آدرس لینک نامعتبر است (لینک‌های مطلق مجاز نیستند)."

        if not errors:
            CommunicationTemplate.objects.create(
                event_key=event_key,
                channel=channel,
                recipient_type=recipient_type,
                title_template=title_template,
                body_template=body_template,
                action_label=action_label,
                action_url_template=action_url_template,
                is_active=is_active,
                is_required=is_required,
                allow_company_toggle=allow_company_toggle,
            )
            return redirect("platform_core:comm_templates")

        # Re-render form with errors
        return render(request, "platform_core/comm_templates/form.html", {
            "is_edit": False,
            "errors": errors,
            "form_data": request.POST,
            "event_key_choices": CommunicationTemplate.EventKey.choices,
            "channel_choices": CommunicationTemplate.Channel.choices,
            "recipient_type_choices": CommunicationTemplate.RecipientType.choices,
        })

    return render(request, "platform_core/comm_templates/form.html", {
        "is_edit": False,
        "errors": {},
        "form_data": {},
        "event_key_choices": CommunicationTemplate.EventKey.choices,
        "channel_choices": CommunicationTemplate.Channel.choices,
        "recipient_type_choices": CommunicationTemplate.RecipientType.choices,
    })


@require_platform_owner
def comm_template_edit(request: HttpRequest, template_id: int) -> HttpResponse:
    """GET: show form with existing data. POST: update template."""
    template = get_object_or_404(CommunicationTemplate, pk=template_id)
    errors = {}

    if request.method == "POST":
        event_key = request.POST.get("event_key", "")
        channel = request.POST.get("channel", "")
        recipient_type = request.POST.get("recipient_type", "")
        title_template = request.POST.get("title_template", "").strip()
        body_template = request.POST.get("body_template", "").strip()
        action_label = request.POST.get("action_label", "").strip()
        action_url_template = request.POST.get("action_url_template", "").strip()
        is_active = request.POST.get("is_active") == "on"
        is_required = request.POST.get("is_required") == "on"
        allow_company_toggle = request.POST.get("allow_company_toggle") == "on"

        # Validation
        if not event_key:
            errors["event_key"] = "رویداد الزامی است."
        if not channel:
            errors["channel"] = "کانال الزامی است."
        if not recipient_type:
            errors["recipient_type"] = "نوع گیرنده الزامی است."
        if not title_template:
            errors["title_template"] = "عنوان الزامی است."
        if not body_template:
            errors["body_template"] = "متن پیام الزامی است."

        # Validate placeholders
        if title_template:
            valid, invalid = CommunicationTemplateService.validate_placeholders(title_template)
            if not valid:
                errors["title_template"] = f"متغیرهای نامعتبر: {', '.join(invalid)}"
        if body_template:
            valid, invalid = CommunicationTemplateService.validate_placeholders(body_template)
            if not valid:
                errors["body_template"] = f"متغیرهای نامعتبر: {', '.join(invalid)}"

        # Validate URL
        if action_url_template and not CommunicationTemplateService.validate_action_url(action_url_template):
            errors["action_url_template"] = "آدرس لینک نامعتبر است (لینک‌های مطلق مجاز نیستند)."

        if not errors:
            template.event_key = event_key
            template.channel = channel
            template.recipient_type = recipient_type
            template.title_template = title_template
            template.body_template = body_template
            template.action_label = action_label
            template.action_url_template = action_url_template
            template.is_active = is_active
            template.is_required = is_required
            template.allow_company_toggle = allow_company_toggle
            template.save()
            return redirect("platform_core:comm_template_detail", template_id=template.pk)

        # Re-render form with errors
        return render(request, "platform_core/comm_templates/form.html", {
            "is_edit": True,
            "template": template,
            "errors": errors,
            "form_data": request.POST,
            "event_key_choices": CommunicationTemplate.EventKey.choices,
            "channel_choices": CommunicationTemplate.Channel.choices,
            "recipient_type_choices": CommunicationTemplate.RecipientType.choices,
        })

    # GET: pre-fill with existing data
    form_data = {
        "event_key": template.event_key,
        "channel": template.channel,
        "recipient_type": template.recipient_type,
        "title_template": template.title_template,
        "body_template": template.body_template,
        "action_label": template.action_label,
        "action_url_template": template.action_url_template,
        "is_active": template.is_active,
        "is_required": template.is_required,
        "allow_company_toggle": template.allow_company_toggle,
    }
    return render(request, "platform_core/comm_templates/form.html", {
        "is_edit": True,
        "template": template,
        "errors": {},
        "form_data": form_data,
        "event_key_choices": CommunicationTemplate.EventKey.choices,
        "channel_choices": CommunicationTemplate.Channel.choices,
        "recipient_type_choices": CommunicationTemplate.RecipientType.choices,
    })


@require_platform_owner
def comm_template_detail(request: HttpRequest, template_id: int) -> HttpResponse:
    """Show template details with rendered preview."""
    template = get_object_or_404(CommunicationTemplate, pk=template_id)

    # Sample context for preview
    sample_context = {
        "company_name": "شرکت نمونه",
        "company_code": "sample-co",
        "operator_name": "علی محمدی",
        "technician_name": "رضا احمدی",
        "order_id": "1234",
        "order_status": "در حال انجام",
        "invoice_id": "INV-5678",
        "invoice_amount": "۱,۵۰۰,۰۰۰",
        "payment_status": "پرداخت شده",
        "sms_balance": "۵۰,۰۰۰",
        "sms_remaining_count": "96",
        "tracking_code": "TRK-9876",
    }

    preview = CommunicationTemplateService.render_template(template, sample_context)

    return render(request, "platform_core/comm_templates/detail.html", {
        "template": template,
        "preview": preview,
    })



@require_platform_owner
def company_templates_list(request: HttpRequest, company_id: int) -> HttpResponse:
    """List all communication templates for a specific company (global inherited + company-specific)."""
    from apps.tenants.models import Company
    company = get_object_or_404(Company, id=company_id)

    # Get all events from global templates
    global_templates = CommunicationTemplate.objects.filter(company__isnull=True, is_active=True)
    company_templates = CommunicationTemplate.objects.filter(company=company)

    # Build unified list
    items = []
    for gtpl in global_templates:
        # Check if company-specific override exists
        override = company_templates.filter(
            event_key=gtpl.event_key, channel=gtpl.channel, recipient_type=gtpl.recipient_type
        ).first()
        items.append({
            "global_template": gtpl,
            "override": override,
            "effective": override if override else gtpl,
            "source": "\u0627\u062e\u062a\u0635\u0627\u0635\u06cc" if override else "\u067e\u06cc\u0634\u200c\u0641\u0631\u0636",
        })

    return render(request, "platform_core/comm_templates/company_list.html", {
        "company": company,
        "items": items,
    })


@require_platform_owner
def company_template_create(request: HttpRequest, company_id: int) -> HttpResponse:
    """Create a company-specific override from global default."""
    from apps.tenants.models import Company

    company = get_object_or_404(Company, id=company_id)

    # Get global template to override (from query param)
    global_id = request.GET.get("from_global") or request.POST.get("from_global")
    global_tpl = None
    if global_id:
        global_tpl = CommunicationTemplate.objects.filter(id=global_id, company__isnull=True).first()

    errors = {}

    if request.method == "POST":
        title = request.POST.get("title_template", "").strip()
        body = request.POST.get("body_template", "").strip()
        action_label = request.POST.get("action_label", "").strip()
        action_url = request.POST.get("action_url_template", "").strip()
        event_key = request.POST.get("event_key", "")
        channel = request.POST.get("channel", "")
        recipient_type = request.POST.get("recipient_type", "")

        # Validate placeholders
        valid_title, invalid_title = CommunicationTemplateService.validate_placeholders(title)
        valid_body, invalid_body = CommunicationTemplateService.validate_placeholders(body)
        if not valid_title or not valid_body:
            errors["placeholders"] = f"\u0645\u062a\u063a\u06cc\u0631\u0647\u0627\u06cc \u063a\u06cc\u0631\u0645\u062c\u0627\u0632: {', '.join(invalid_title + invalid_body)}"

        # Validate URL
        if action_url and not CommunicationTemplateService.validate_action_url(action_url):
            errors["action_url"] = "\u0622\u062f\u0631\u0633 \u0641\u0642\u0637 \u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u062f \u062f\u0627\u062e\u0644\u06cc \u0628\u0627\u0634\u062f (\u0628\u062f\u0648\u0646 http/https)."

        if not errors and title and body:
            CommunicationTemplate.objects.create(
                company=company,
                event_key=event_key,
                channel=channel,
                recipient_type=recipient_type,
                title_template=title,
                body_template=body,
                action_label=action_label,
                action_url_template=action_url,
                is_active=True,
                is_required=request.POST.get("is_required") == "on",
                allow_company_toggle=request.POST.get("allow_company_toggle") == "on",
            )
            return redirect("platform_core:company_comm_templates", company_id=company.id)

    # Pre-fill from global template
    prefill = {}
    if global_tpl:
        prefill = {
            "event_key": global_tpl.event_key,
            "channel": global_tpl.channel,
            "recipient_type": global_tpl.recipient_type,
            "title_template": global_tpl.title_template,
            "body_template": global_tpl.body_template,
            "action_label": global_tpl.action_label,
            "action_url_template": global_tpl.action_url_template,
        }

    return render(request, "platform_core/comm_templates/company_form.html", {
        "company": company,
        "prefill": prefill,
        "global_tpl": global_tpl,
        "errors": errors,
        "is_edit": False,
    })


@require_platform_owner
def company_template_edit(request: HttpRequest, company_id: int, template_id: int) -> HttpResponse:
    """Edit a company-specific template."""
    from apps.tenants.models import Company

    company = get_object_or_404(Company, id=company_id)
    tpl = get_object_or_404(CommunicationTemplate, id=template_id, company=company)
    errors = {}

    if request.method == "POST":
        title = request.POST.get("title_template", "").strip()
        body = request.POST.get("body_template", "").strip()
        action_label = request.POST.get("action_label", "").strip()
        action_url = request.POST.get("action_url_template", "").strip()

        valid_title, invalid_title = CommunicationTemplateService.validate_placeholders(title)
        valid_body, invalid_body = CommunicationTemplateService.validate_placeholders(body)
        if not valid_title or not valid_body:
            errors["placeholders"] = f"\u0645\u062a\u063a\u06cc\u0631\u0647\u0627\u06cc \u063a\u06cc\u0631\u0645\u062c\u0627\u0632: {', '.join(invalid_title + invalid_body)}"

        if action_url and not CommunicationTemplateService.validate_action_url(action_url):
            errors["action_url"] = "\u0622\u062f\u0631\u0633 \u0641\u0642\u0637 \u0645\u06cc\u200c\u062a\u0648\u0627\u0646\u062f \u062f\u0627\u062e\u0644\u06cc \u0628\u0627\u0634\u062f."

        if not errors:
            tpl.title_template = title
            tpl.body_template = body
            tpl.action_label = action_label
            tpl.action_url_template = action_url
            tpl.is_active = request.POST.get("is_active") == "on"
            tpl.is_required = request.POST.get("is_required") == "on"
            tpl.allow_company_toggle = request.POST.get("allow_company_toggle") == "on"
            tpl.save()
            return redirect("platform_core:company_comm_templates", company_id=company.id)

    return render(request, "platform_core/comm_templates/company_form.html", {
        "company": company,
        "tpl": tpl,
        "prefill": {
            "event_key": tpl.event_key,
            "channel": tpl.channel,
            "recipient_type": tpl.recipient_type,
            "title_template": tpl.title_template,
            "body_template": tpl.body_template,
            "action_label": tpl.action_label,
            "action_url_template": tpl.action_url_template,
        },
        "errors": errors,
        "is_edit": True,
    })


@require_platform_owner
def company_template_reset(request: HttpRequest, company_id: int, template_id: int) -> HttpResponse:
    """Reset (delete) a company-specific override back to global default."""
    from apps.tenants.models import Company
    company = get_object_or_404(Company, id=company_id)
    tpl = get_object_or_404(CommunicationTemplate, id=template_id, company=company)

    if request.method == "POST":
        tpl.delete()

    return redirect("platform_core:company_comm_templates", company_id=company.id)
