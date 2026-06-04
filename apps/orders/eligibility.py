"""
Orders - Eligibility and Visibility Helpers.

Centralized business rules for technician order visibility.

This module is intentionally small and reusable because the same rules are used by:
- technician available-orders selectors
- technician order detail permissions
- technician accept preconditions
- order creation/recycle services that need priority visibility timestamps

IMPORTANT:
- Always keep tenant isolation checks here.
- Do not put HTTP/request logic in this module.
"""
from datetime import timedelta
from typing import Optional, Tuple

from django.conf import settings as django_settings
from django.utils import timezone

from apps.accounts.models import Technician, TechnicianCategorySkill, TechnicianSkill
from apps.tenants.selectors import get_company_settings

from .models import Order


LEGACY_TECHNICIAN_MAX_ACTIVE_ORDERS = getattr(
    django_settings, "TECHNICIAN_MAX_ACTIVE_ORDERS", 5,
)
ACTIVE_TECHNICIAN_STATUSES = [Order.Status.WAITING, Order.Status.IN_PROGRESS]


def calculate_priority_visibility_times(*, company, base_time=None) -> Tuple[object, object]:
    """
    Calculate delayed visibility timestamps for priority-2 and priority-3 technicians.

    Args:
        company: Tenant company whose settings control delays.
        base_time: Datetime to start from. Defaults to timezone.now().

    Returns:
        tuple(priority2_visible_at, priority3_visible_at)
    """
    if base_time is None:
        base_time = timezone.now()

    company_settings = get_company_settings(company)
    return (
        base_time + timedelta(minutes=company_settings.priority2_delay_minutes),
        base_time + timedelta(minutes=company_settings.priority3_delay_minutes),
    )


def set_missing_priority_visibility_times(*, order: Order, base_time=None) -> Order:
    """
    Fill missing priority visibility timestamps on a NEW order.

    This keeps service-layer creation safe without moving all business logic into
    Order.save(). Existing explicit timestamps are preserved.
    """
    if order.status != Order.Status.NEW:
        return order

    priority2_visible_at, priority3_visible_at = calculate_priority_visibility_times(
        company=order.company,
        base_time=base_time,
    )
    if order.priority2_visible_at is None:
        order.priority2_visible_at = priority2_visible_at
    if order.priority3_visible_at is None:
        order.priority3_visible_at = priority3_visible_at
    return order


def _as_local_date(dt):
    """Return a safe local date for aware or naive datetimes."""
    if dt is None:
        return None
    if timezone.is_aware(dt):
        return timezone.localtime(dt).date()
    return dt.date()


def get_order_service_date(order: Order):
    """Return the operational service date, preferring service_date over scheduled_for."""
    if getattr(order, "service_date", None) is not None:
        return order.service_date
    return _as_local_date(order.scheduled_for)


def is_future_order_visible(*, order: Order, company_settings=None, now=None) -> bool:
    """
    Check whether a scheduled future order is visible to technicians.

    Rules:
    - Orders with no scheduled_for are visible.
    - Orders scheduled for today or the past are visible.
    - Future orders are hidden unless the company enables them.
    - If a daily time gate is configured, future orders are visible only after it.
    """
    if now is None:
        now = timezone.now()

    scheduled_date = get_order_service_date(order)
    if scheduled_date is None:
        return True

    today = timezone.localdate(now)
    if scheduled_date <= today:
        return True

    if company_settings is None:
        company_settings = get_company_settings(order.company)

    if not company_settings.show_future_orders_to_technicians:
        return False

    visible_after = company_settings.future_orders_visible_after
    if visible_after is None:
        return True

    return timezone.localtime(now).time() >= visible_after


def _active_order_limit_reached(*, technician: Technician, limit: int) -> bool:
    """Return True when the technician has reached a positive active-order limit."""
    if limit <= 0:
        return False

    active_count = Order.objects.filter(
        company=technician.company,
        technician=technician,
        status__in=ACTIVE_TECHNICIAN_STATUSES,
    ).count()
    return active_count >= limit


def _is_category_order_visible_to_technician(
    *,
    order: Order,
    technician: Technician,
    company_settings,
    now,
) -> bool:
    """Category/priority-based visibility used by the SaaS order engine."""
    if order.service_category_id is None:
        return False

    category_skill = TechnicianCategorySkill.objects.filter(
        technician=technician,
        category_id=order.service_category_id,
    ).first()
    if category_skill is None:
        return False

    if _active_order_limit_reached(
        technician=technician,
        limit=company_settings.max_active_orders_per_technician,
    ):
        return False

    if category_skill.priority == TechnicianCategorySkill.Priority.P2:
        if order.priority2_visible_at is None or order.priority2_visible_at > now:
            return False

    if category_skill.priority == TechnicianCategorySkill.Priority.P3:
        if order.priority3_visible_at is None or order.priority3_visible_at > now:
            return False

    return is_future_order_visible(
        order=order,
        company_settings=company_settings,
        now=now,
    )


def _is_legacy_skill_order_visible_to_technician(
    *,
    order: Order,
    technician: Technician,
    company_settings,
    now,
) -> bool:
    """
    Backward-compatible visibility for older orders that only use required_skill.

    Legacy orders have no service_category. They remain visible only when the
    technician satisfies the legacy skill rule and workload/future-order gates.
    """
    if _active_order_limit_reached(
        technician=technician,
        limit=LEGACY_TECHNICIAN_MAX_ACTIVE_ORDERS,
    ):
        return False

    if order.required_skill:
        has_skill = TechnicianSkill.objects.filter(
            technician=technician,
            name=order.required_skill,
        ).exists()
        if not has_skill:
            return False

    return is_future_order_visible(
        order=order,
        company_settings=company_settings,
        now=now,
    )


def is_order_visible_to_technician(
    *,
    order: Order,
    technician: Optional[Technician],
    now=None,
) -> bool:
    """
    Check whether a technician may see a NEW unassigned order.

    This is the safe single-order equivalent of the available-orders selector.
    Use it for direct detail URLs and accept button permissions to avoid leaking
    hidden NEW orders by guessed IDs.
    """
    if technician is None:
        return False

    if now is None:
        now = timezone.now()

    # Tenant isolation and base order state.
    if order.company_id != technician.company_id:
        return False
    if order.status != Order.Status.NEW:
        return False
    if order.technician_id is not None:
        return False
    if not technician.is_available:
        return False

    company_settings = get_company_settings(order.company)

    if order.service_category_id is not None:
        return _is_category_order_visible_to_technician(
            order=order,
            technician=technician,
            company_settings=company_settings,
            now=now,
        )

    return _is_legacy_skill_order_visible_to_technician(
        order=order,
        technician=technician,
        company_settings=company_settings,
        now=now,
    )


def is_order_accept_allowed_by_service_date(*, order: Order, company_settings=None, now=None) -> bool:
    """
    Accept/assignment gate for technician self-accept.

    Future-dated orders may be visible, but should not be accepted before their
    service date. On the service date, the configured daily gate time applies.
    Admin manual assignment intentionally bypasses this check.
    """
    if now is None:
        now = timezone.now()

    service_date = get_order_service_date(order)
    if service_date is None:
        return True

    today = timezone.localdate(now)
    if service_date < today:
        return True
    if service_date > today:
        return False

    if company_settings is None:
        company_settings = get_company_settings(order.company)

    gate = company_settings.future_orders_visible_after
    if gate is None:
        return True
    return timezone.localtime(now).time() >= gate
