# Auto-generated notification event signals.
# Business apps should not import SMS directly.
from __future__ import annotations

from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.invoices.models import Invoice
from apps.notifications.event_catalog import EventKey
from apps.notifications.services_events import NotificationEventService


SUCCESS_STATUSES = {
    "paid",
    "verified",
    "success",
    "successful",
    "completed",
    "settled",
}

FAILED_STATUSES = {
    "failed",
    "payment_failed",
    "cancelled",
    "canceled",
    "rejected",
}


def _status_value(instance) -> str:
    return str(getattr(instance, "status", "") or "").strip().lower()


def _emit_safely(*, event_key: str, company=None, actor=None, target=None, payload=None, dedup_extra: str = ""):
    try:
        dedup_key = NotificationEventService.build_dedup_key(
            event_key=event_key,
            target=target,
            extra=dedup_extra,
        )
        return NotificationEventService.emit(
            event_key=event_key,
            company=company or getattr(target, "company", None),
            actor=actor,
            target=target,
            payload=payload or {},
            dedup_key=dedup_key,
        )
    except Exception:
        return None


@receiver(post_save, sender=Invoice)
def emit_invoice_status_events(sender, instance, created, **kwargs):
    """Emit invoice/payment events when invoice status changes.

    NotificationEventService deduplication prevents duplicate outbox rows for
    repeated saves with the same status.
    """
    status = _status_value(instance)
    if not status:
        return

    if status == "issued":
        _emit_safely(
            event_key=EventKey.INVOICE_ISSUED_CUSTOMER,
            company=getattr(instance, "company", None),
            target=instance,
            payload={"invoice_status": status},
        )
        return

    if status in SUCCESS_STATUSES:
        _emit_safely(
            event_key=EventKey.INVOICE_PAID_CUSTOMER,
            company=getattr(instance, "company", None),
            target=instance,
            payload={"invoice_status": status},
        )
        _emit_safely(
            event_key=EventKey.PAYMENT_SUCCESS_CUSTOMER,
            company=getattr(instance, "company", None),
            target=instance,
            payload={"invoice_status": status},
            dedup_extra="payment",
        )
        return

    if status in FAILED_STATUSES:
        _emit_safely(
            event_key=EventKey.PAYMENT_FAILED_CUSTOMER,
            company=getattr(instance, "company", None),
            target=instance,
            payload={"invoice_status": status},
        )


# ---------------------------------------------------------------------------
# Lightweight business-object creation signals
# ---------------------------------------------------------------------------
# These only create NotificationEvent/SMSOutbox records through the central
# event pipeline. They do not send real SMS and they do not change UI/business
# behavior.


def _connect_creation_signals():
    try:
        from apps.accounts.models import CompanyUser, Technician, UserRole
        from apps.tenants.models import CompanyServiceCategory
        from apps.orders.models import OrderItemDefinition
    except Exception:
        return

    @receiver(post_save, sender=CompanyUser, weak=False)
    def emit_operator_created_event(sender, instance, created, **kwargs):
        if not created:
            return
        if getattr(instance, "role", "") != UserRole.COMPANY_STAFF:
            return
        _emit_safely(
            event_key=EventKey.OPERATOR_CREATED,
            company=getattr(instance, "company", None),
            target=instance,
            payload={
                "operator_name": instance.get_full_name() if hasattr(instance, "get_full_name") else getattr(instance, "username", ""),
                "username": getattr(instance, "username", ""),
            },
        )

    @receiver(post_save, sender=Technician, weak=False)
    def emit_technician_created_event(sender, instance, created, **kwargs):
        if not created:
            return
        user = getattr(instance, "user", None)
        _emit_safely(
            event_key=EventKey.TECHNICIAN_CREATED,
            company=getattr(instance, "company", None),
            target=instance,
            payload={
                "technician_name": user.get_full_name() if user and hasattr(user, "get_full_name") else getattr(user, "username", ""),
                "username": getattr(user, "username", "") if user else "",
            },
        )

    @receiver(post_save, sender=CompanyServiceCategory, weak=False)
    def emit_service_category_created_event(sender, instance, created, **kwargs):
        if not created:
            return
        _emit_safely(
            event_key=EventKey.SERVICE_CATEGORY_CREATED,
            company=getattr(instance, "company", None),
            target=instance,
            payload={
                "service_category": getattr(instance, "title", ""),
                "category_title": getattr(instance, "title", ""),
            },
        )

    @receiver(post_save, sender=OrderItemDefinition, weak=False)
    def emit_service_item_created_event(sender, instance, created, **kwargs):
        if not created:
            return
        category = getattr(instance, "category", None)
        _emit_safely(
            event_key=EventKey.SERVICE_ITEM_CREATED,
            company=getattr(instance, "company", None),
            target=instance,
            payload={
                "item_title": getattr(instance, "title", ""),
                "item_kind": getattr(instance, "kind", ""),
                "service_category": getattr(category, "title", ""),
            },
        )


_connect_creation_signals()


# ---------------------------------------------------------------------------
# Backward compatibility hook
# ---------------------------------------------------------------------------
def connect_sms_template_signal():
    """
    Compatibility hook called by apps.notifications.apps.NotificationsConfig.ready().

    The actual notification/payment signal receivers in this module are connected
    automatically when this module is imported by Django. This function exists so
    older app startup code that calls signals.connect_sms_template_signal() keeps
    working without crashing.
    """
    return None
