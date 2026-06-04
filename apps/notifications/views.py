"""
Notifications - Views.

Thin views for notification list and mark-as-read.
"""
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.permissions import require_tenant_auth

from .models import Notification
from .selectors import NotificationSelector
from .services import NotificationMarkReadService


@require_tenant_auth
def notification_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """List notifications for the current user."""
    company = request.company
    notifications = NotificationSelector.get_for_user(
        company=company, user=request.user
    )
    unread_count = NotificationSelector.get_unread_count(
        company=company, user=request.user
    )
    return render(request, "notifications/list.html", {
        "notifications": notifications,
        "unread_count": unread_count,
        "company": company,
    })


@require_tenant_auth
def notification_mark_read(request: HttpRequest, notification_id: int, **kwargs) -> HttpResponse:
    """Mark a single notification as read."""
    company = request.company
    notification = Notification.objects.filter(
        id=notification_id, company=company, recipient=request.user
    ).first()

    if notification is None:
        raise Http404("Notification not found.")

    NotificationMarkReadService.mark_read(notification=notification)
    if getattr(request.user, "role", None) == "TECHNICIAN":
        return redirect(f"/{company.code}/tech/notifications/")
    if getattr(request.user, "role", None) in {"COMPANY_ADMIN", "COMPANY_STAFF"}:
        return redirect(f"/{company.code}/admin/notifications/")
    return redirect(f"/{company.code}/notifications/")
