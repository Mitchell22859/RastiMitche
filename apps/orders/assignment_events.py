"""Post-assignment event hooks for order workflow.

Side effects run after commit and go through the central NotificationEventService.
Order code must not import SMS directly.
"""
from __future__ import annotations

from django.db import transaction


def dispatch_order_assigned_events(*, order, technician) -> None:
    """Run notification hooks after an admin/staff assignment is committed."""
    transaction.on_commit(lambda: _run_order_assigned_events(order_id=order.id, technician_id=technician.id))


def _run_order_assigned_events(*, order_id: int, technician_id: int) -> None:
    from apps.accounts.models import Technician
    from apps.notifications.models import Notification, NotificationSetting
    from apps.notifications.services import NotificationCreateService
    from apps.notifications.event_catalog import EventKey
    from apps.notifications.services_events import NotificationEventService
    from apps.orders.models import Order

    order = Order.objects.select_related("company", "customer", "technician").filter(id=order_id).first()
    technician = Technician.objects.select_related("user", "company").filter(id=technician_id).first()
    if order is None or technician is None:
        return

    if technician.user_id:
        try:
            NotificationCreateService.create(
                company=order.company,
                recipient=technician.user,
                notification_type=Notification.NotificationType.ORDER_ASSIGNED,
                title="سفارش جدید به شما تخصیص داده شد",
                message=f"سفارش #{order.id} برای {order.display_customer_name or 'مشتری'} به شما تخصیص داده شد.",
                related_order=order,
                event_key=NotificationSetting.EventKey.ORDER_ASSIGNED_TECHNICIAN,
            )
        except Exception:
            pass

    try:
        NotificationEventService.emit(
            event_key=EventKey.ORDER_ASSIGNED_TECHNICIAN,
            company=order.company,
            target=order,
            payload={"technician_id": technician.id},
            dedup_key=f"order_assigned_technician:order:{order.id}:technician:{technician.id}",
            use_on_commit=False,
        )
    except Exception:
        pass

    try:
        NotificationEventService.emit(
            event_key=EventKey.ORDER_ACCEPTED_CUSTOMER,
            company=order.company,
            target=order,
            payload={"technician_id": technician.id},
            dedup_key=f"order_accepted_customer:order:{order.id}",
            use_on_commit=False,
        )
    except Exception:
        pass
