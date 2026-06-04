"""Cancel request event dispatchers.

In-app notifications are still created for staff/technicians.
SMS is routed only through NotificationEventService.
"""
from __future__ import annotations

from django.db import transaction


def dispatch_cancel_request_events(*, order, reason: str = "") -> None:
    transaction.on_commit(lambda: _run_cancel_request_events(order_id=order.id, reason=reason))


def dispatch_cancel_approved_events(*, order) -> None:
    transaction.on_commit(lambda: _run_cancel_approved_events(order_id=order.id))


def dispatch_cancel_rejected_events(*, order) -> None:
    transaction.on_commit(lambda: _run_cancel_rejected_events(order_id=order.id))


def _run_cancel_request_events(*, order_id: int, reason: str) -> None:
    from apps.accounts.models import CompanyUser, UserRole
    from apps.notifications.models import Notification, NotificationSetting
    from apps.notifications.services import NotificationCreateService
    from apps.notifications.event_catalog import EventKey
    from apps.notifications.services_events import NotificationEventService
    from apps.orders.models import Order

    order = (
        Order.objects.select_related("company", "technician", "technician__user")
        .filter(id=order_id)
        .first()
    )
    if order is None:
        return

    tech_name = ""
    if order.technician and order.technician.user:
        tech_name = order.technician.user.get_full_name()

    title = "درخواست لغو سفارش"
    message = (
        f"تکنسین {tech_name} درخواست لغو سفارش #{order.id} "
        f"({order.display_customer_name or '-'}) را ثبت کرد."
    )
    if reason:
        message += f"\nدلیل: {reason}"

    admins = CompanyUser.objects.filter(
        company=order.company,
        role__in=[UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF],
        is_active=True,
    )
    for admin in admins:
        try:
            NotificationCreateService.create(
                company=order.company,
                recipient=admin,
                notification_type=Notification.NotificationType.ORDER_CANCEL_REQUESTED,
                title=title,
                message=message,
                related_order=order,
                event_key=NotificationSetting.EventKey.ORDER_CANCEL_REQUESTED_ADMIN,
            )
        except Exception:
            pass

    try:
        NotificationEventService.emit(
            event_key=EventKey.ORDER_CANCEL_REQUESTED_ADMIN,
            company=order.company,
            target=order,
            payload={"reason": reason or ""},
            dedup_key=f"order_cancel_requested_admin:order:{order.id}",
            use_on_commit=False,
        )
    except Exception:
        pass


def _run_cancel_approved_events(*, order_id: int) -> None:
    from apps.notifications.models import Notification, NotificationSetting
    from apps.notifications.services import NotificationCreateService
    from apps.notifications.event_catalog import EventKey
    from apps.notifications.services_events import NotificationEventService
    from apps.orders.models import Order

    order = (
        Order.objects.select_related("company", "technician", "technician__user")
        .filter(id=order_id)
        .first()
    )
    if order is None:
        return

    tech_user = order.technician.user if order.technician and order.technician.user else None
    if tech_user is None:
        return

    try:
        NotificationCreateService.create(
            company=order.company,
            recipient=tech_user,
            notification_type=Notification.NotificationType.ORDER_CANCEL_APPROVED,
            title="درخواست لغو تایید شد",
            message=f"درخواست لغو سفارش #{order.id} توسط مدیر تایید شد.",
            related_order=order,
            event_key=NotificationSetting.EventKey.ORDER_CANCEL_APPROVED_TECHNICIAN,
        )
    except Exception:
        pass

    try:
        NotificationEventService.emit(
            event_key=EventKey.ORDER_CANCEL_APPROVED_TECHNICIAN,
            company=order.company,
            target=order,
            dedup_key=f"order_cancel_approved_technician:order:{order.id}",
            use_on_commit=False,
        )
    except Exception:
        pass


def _run_cancel_rejected_events(*, order_id: int) -> None:
    from apps.notifications.models import Notification, NotificationSetting
    from apps.notifications.services import NotificationCreateService
    from apps.notifications.event_catalog import EventKey
    from apps.notifications.services_events import NotificationEventService
    from apps.orders.models import Order

    order = (
        Order.objects.select_related("company", "technician", "technician__user")
        .filter(id=order_id)
        .first()
    )
    if order is None:
        return

    tech_user = order.technician.user if order.technician and order.technician.user else None
    if tech_user is None:
        return

    try:
        NotificationCreateService.create(
            company=order.company,
            recipient=tech_user,
            notification_type=Notification.NotificationType.ORDER_CANCEL_REJECTED,
            title="درخواست لغو رد شد",
            message=(
                f"درخواست لغو سفارش #{order.id} توسط مدیر رد شد. "
                f"سفارش به وضعیت قبلی بازگشت."
            ),
            related_order=order,
            event_key=NotificationSetting.EventKey.ORDER_CANCEL_REJECTED_TECHNICIAN,
        )
    except Exception:
        pass

    try:
        NotificationEventService.emit(
            event_key=EventKey.ORDER_CANCEL_REJECTED_TECHNICIAN,
            company=order.company,
            target=order,
            dedup_key=f"order_cancel_rejected_technician:order:{order.id}",
            use_on_commit=False,
        )
    except Exception:
        pass
