"""
Platform Core - Message Center Views.

Internal message center for Platform Owner.
No real SMS/email delivery — messages stored locally only.

TODO (Future):
- Connect channel=SMS_FUTURE to real SMS provider
- Connect channel=EMAIL_FUTURE to real email provider
- Add bulk send capability
- Add scheduled sending
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.permissions import require_platform_owner
from apps.tenants.models import Company

from .models import PlatformMessage


@require_platform_owner
def message_index(request: HttpRequest) -> HttpResponse:
    """Message center home — redirects to inbox."""
    return redirect("platform_core:messages_inbox")


@require_platform_owner
def message_inbox(request: HttpRequest) -> HttpResponse:
    """List inbound messages."""
    messages = PlatformMessage.objects.filter(
        direction=PlatformMessage.Direction.INBOUND
    )
    return render(request, "platform_core/messages/inbox.html", {
        "messages": messages,
    })


@require_platform_owner
def message_outbox(request: HttpRequest) -> HttpResponse:
    """List outbound messages."""
    messages = PlatformMessage.objects.filter(
        direction=PlatformMessage.Direction.OUTBOUND
    )
    return render(request, "platform_core/messages/outbox.html", {
        "messages": messages,
    })


@require_platform_owner
def message_create(request: HttpRequest) -> HttpResponse:
    """Compose a new message."""
    companies = Company.objects.filter(is_active=True).order_by("name")

    if request.method == "POST":
        subject = request.POST.get("subject", "").strip()
        body = request.POST.get("body", "").strip()
        recipient_type = request.POST.get("recipient_type", "COMPANY")
        recipient_company_id = request.POST.get("recipient_company")
        action = request.POST.get("action", "send")

        errors = {}
        if not subject:
            errors["subject"] = "عنوان پیام الزامی است."
        if not body:
            errors["body"] = "متن پیام الزامی است."

        if errors:
            return render(request, "platform_core/messages/create.html", {
                "companies": companies,
                "errors": errors,
                "form_data": request.POST,
            })

        # Create the message
        status = PlatformMessage.Status.DRAFT if action == "draft" else PlatformMessage.Status.SENT
        msg = PlatformMessage.objects.create(
            sender=request.user,
            recipient_type=recipient_type,
            recipient_company_id=recipient_company_id or None,
            channel=PlatformMessage.Channel.INTERNAL,
            direction=PlatformMessage.Direction.OUTBOUND,
            subject=subject,
            body=body,
            status=status,
            sent_at=timezone.now() if status == PlatformMessage.Status.SENT else None,
        )
        return redirect("platform_core:messages_outbox")

    return render(request, "platform_core/messages/create.html", {
        "companies": companies,
        "errors": {},
        "form_data": {},
    })


@require_platform_owner
def message_detail(request: HttpRequest, message_id: int) -> HttpResponse:
    """View a single message."""
    msg = get_object_or_404(PlatformMessage, id=message_id)

    # Mark as read if inbound and unread
    if msg.direction == PlatformMessage.Direction.INBOUND and msg.status != PlatformMessage.Status.READ:
        msg.status = PlatformMessage.Status.READ
        msg.read_at = timezone.now()
        msg.save(update_fields=["status", "read_at", "updated_at"])

    return render(request, "platform_core/messages/detail.html", {
        "msg": msg,
    })
