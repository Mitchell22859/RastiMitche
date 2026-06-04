"""Order event dispatchers.

Database writes happen inside services; external side effects are scheduled via
transaction.on_commit so notifications/SMS are sent only after the order is
successfully committed.
"""
from __future__ import annotations

from django.db import transaction


def dispatch_order_available_events(*, order) -> None:
    transaction.on_commit(lambda: _run_order_available_events(order_id=order.id))


def _run_order_available_events(*, order_id: int) -> None:
    from apps.notifications.event_catalog import EventKey
    from apps.notifications.services_events import NotificationEventService
    from apps.orders.models import Order
    from apps.orders.technician_notifications import notify_visible_technicians_for_order

    order = Order.objects.select_related(
        "company", "customer", "service_category", "technician",
    ).filter(id=order_id).first()
    if order is None:
        return

    try:
        notify_visible_technicians_for_order(order=order)
    except Exception:
        pass

    try:
        NotificationEventService.emit(
            event_key=EventKey.ORDER_AVAILABLE_TECHNICIAN,
            company=order.company,
            target=order,
            dedup_key=f"order_available_technician:order:{order.id}",
            use_on_commit=False,
        )
    except Exception:
        pass
