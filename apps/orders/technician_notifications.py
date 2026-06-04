"""Technician-facing order notification helpers.

This module contains the routing logic for notifying field technicians about
newly available orders. It intentionally reuses the same eligibility rules used
by order visibility, so notifications do not leak hidden/unavailable orders.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.utils import timezone

from apps.accounts.models import Technician, TechnicianCategorySkill
from apps.notifications.models import Notification
from apps.notifications.services import NotificationCreateService, NotificationSettingService
from apps.sms.models import SMSOutbox, SMSTemplate
from apps.sms.services import SMSQueueService

from .eligibility import is_order_accept_allowed_by_service_date, is_order_visible_to_technician
from .models import Order


@dataclass(frozen=True)
class TechnicianNotificationResult:
    """Small result object returned by dispatch helpers."""

    technician_id: int
    in_app_created: bool
    sms_queued: bool


@dataclass(frozen=True)
class TechnicianDispatchSummary:
    """Aggregate result for automatic/company-wide dispatch runs."""

    checked_orders: int = 0
    created_notifications: int = 0
    queued_sms: int = 0


def _get_candidate_technicians_for_order(*, order: Order) -> Iterable[Technician]:
    """Return active technicians mapped to the order category.

    The final visibility decision is still made by
    ``is_order_visible_to_technician``. This query is only a narrow candidate
    set so we do not scan all technicians in the tenant.
    """
    if not order.service_category_id:
        return Technician.objects.none()

    skill_qs = TechnicianCategorySkill.objects.filter(
        category_id=order.service_category_id,
        technician__company=order.company,
        technician__is_available=True,
        technician__user__isnull=False,
    ).select_related("technician", "technician__user")

    technician_ids = [skill.technician_id for skill in skill_qs]
    if not technician_ids:
        return Technician.objects.none()

    return Technician.objects.filter(
        id__in=technician_ids,
        company=order.company,
        is_available=True,
        user__isnull=False,
    ).select_related("user")


def _build_available_order_message(*, order: Order, can_accept_now: bool) -> str:
    customer = order.display_customer_name or "-"
    address = order.address or "-"
    category = order.service_category.title if order.service_category_id else "-"

    if can_accept_now:
        action_text = "این سفارش اکنون قابل پذیرش است."
    else:
        action_text = "این سفارش فعلاً فقط قابل مشاهده است و در زمان مجاز قابل پذیرش می‌شود."

    return (
        f"سفارش جدید #{order.id}\n"
        f"رسته: {category}\n"
        f"مشتری: {customer}\n"
        f"آدرس: {address}\n"
        f"{action_text}"
    )


def notify_visible_technicians_for_order(
    *,
    order: Order,
    now=None,
    send_sms: bool = True,
) -> list[TechnicianNotificationResult]:
    """Notify technicians who may currently see a NEW unassigned order.

    Duplicate protection:
    - In-app notification is created only once per technician/order/type.
    - Technician SMS is queued only when the in-app notification is newly
      created, so repeated cron/management-command runs do not spam workers.

    Future orders:
    - Visibility uses company settings.
    - Acceptability is checked separately, so a visible future order can be
      announced as "view-only" until the service date/gate allows acceptance.
    """
    if now is None:
        now = timezone.now()

    if order.status != Order.Status.NEW or order.technician_id is not None:
        return []
    if not order.service_category_id:
        return []

    results: list[TechnicianNotificationResult] = []

    for technician in _get_candidate_technicians_for_order(order=order):
        if not is_order_visible_to_technician(order=order, technician=technician, now=now):
            continue

        recipient = technician.user
        notification_type = Notification.NotificationType.ORDER_AVAILABLE
        event_key = SMSTemplate.TemplateKey.ORDER_AVAILABLE_TECHNICIAN
        already_exists = Notification.objects.filter(
            company=order.company,
            recipient=recipient,
            related_order=order,
            notification_type=notification_type,
        ).exists()

        created = False
        sms_queued = False
        if not already_exists:
            can_accept_now = is_order_accept_allowed_by_service_date(order=order, now=now)
            notification = NotificationCreateService.create(
                company=order.company,
                recipient=recipient,
                notification_type=notification_type,
                title="سفارش جدید قابل مشاهده است",
                message=_build_available_order_message(order=order, can_accept_now=can_accept_now),
                related_order=order,
                event_key=event_key,
            )
            created = notification is not None

            if False and send_sms and NotificationSettingService.is_sms_enabled(
                company=order.company,
                event_key=event_key,
            ):
                phone = getattr(recipient, "phone", "") or ""
                if phone:
                    sms_already_exists = SMSOutbox.objects.filter(
                        company=order.company,
                        phone_number=phone,
                        template_key=event_key,
                        order_id=order.id,
                    ).exists()
                    if not sms_already_exists:
                        sms = SMSQueueService.queue(
                            company=order.company,
                            phone_number=phone,
                            message=(
                                f"سفارش جدید #{order.id} در رسته "
                                f"{order.service_category.title if order.service_category_id else '-'} "
                                f"برای شما قابل مشاهده است."
                            ),
                            template_key=event_key,
                            order_id=order.id,
                        )
                        sms_queued = sms is not None

        results.append(TechnicianNotificationResult(
            technician_id=technician.id,
            in_app_created=created,
            sms_queued=sms_queued,
        ))

    return results


def dispatch_due_order_notifications_for_company(
    *,
    company,
    now=None,
    send_sms: bool = True,
) -> TechnicianDispatchSummary:
    """Dispatch due technician notifications for all currently visible NEW orders.

    This is the automatic replacement for the manual management command. It is
    intentionally idempotent: ``notify_visible_technicians_for_order`` prevents
    duplicate in-app notifications and duplicate SMS queue records for the same
    order/technician pair.

    Without Celery/cron this function can be called lazily from technician/admin
    page requests. When a real background worker is added later, the worker can
    call this same function on a schedule.
    """
    if now is None:
        now = timezone.now()

    orders = Order.objects.filter(
        company=company,
        status=Order.Status.NEW,
        technician__isnull=True,
        service_category__isnull=False,
    ).select_related("company", "customer", "service_category")

    checked_orders = 0
    created_notifications = 0
    queued_sms = 0

    for order in orders:
        checked_orders += 1
        results = notify_visible_technicians_for_order(
            order=order,
            now=now,
            send_sms=send_sms,
        )
        created_notifications += sum(1 for row in results if row.in_app_created)
        queued_sms += sum(1 for row in results if row.sms_queued)

    return TechnicianDispatchSummary(
        checked_orders=checked_orders,
        created_notifications=created_notifications,
        queued_sms=queued_sms,
    )
