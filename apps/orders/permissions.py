"""
Orders - Permissions.

Centralized permission checks for order operations.
All access control for orders is defined HERE — not in views.

Rules:
- Admin/Staff can view all company orders
- Technician can only view assigned orders + visible (NEW) orders
- Customer can only view their own orders
- No cross-company access ever
"""
from apps.accounts.models import CompanyUser, UserRole

from apps.tenants.selectors import get_company_settings

from .eligibility import (
    is_order_accept_allowed_by_service_date,
    is_order_visible_to_technician,
)
from .models import Order


def can_view_order(*, user: CompanyUser, order: Order) -> bool:
    """
    Check if user can view a specific order.

    Rules:
    - User must belong to the same company as the order.
    - COMPANY_ADMIN / COMPANY_STAFF: can view any order in their company.
    - TECHNICIAN: can view orders assigned to them.
    - CUSTOMER: can view their own orders only.
    """
    # Tenant isolation
    if user.company_id != order.company_id:
        return False

    if user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
        return True

    if user.role == UserRole.TECHNICIAN:
        technician = getattr(user, "technician_profile", None)
        if technician and order.technician_id == technician.id:
            return True
        # A technician may view a NEW unassigned order only when every
        # visibility/eligibility rule passes. This prevents detail leakage
        # through guessed order IDs.
        return is_order_visible_to_technician(order=order, technician=technician)

    if user.role == UserRole.CUSTOMER:
        customer = getattr(user, "customer_profile", None)
        if customer and order.customer_id == customer.id:
            return True
        return False

    return False


def can_accept_order(*, user: CompanyUser, order: Order) -> bool:
    """
    Check if user can accept (claim) an order.

    Rules:
    - User must be a TECHNICIAN
    - User must belong to the same company as the order
    - Order must be NEW, unassigned, and visible to this technician
    """
    if user.company_id != order.company_id:
        return False

    if user.role != UserRole.TECHNICIAN:
        return False

    technician = getattr(user, "technician_profile", None)
    if not is_order_visible_to_technician(order=order, technician=technician):
        return False

    # Future orders may be visible to technicians but must not be accepted
    # before the configured service-date gate.
    company_settings = get_company_settings(order.company)
    return is_order_accept_allowed_by_service_date(
        order=order,
        company_settings=company_settings,
    )


def can_complete_order(*, user: CompanyUser, order: Order) -> bool:
    """
    Check if user can mark an order as complete.

    Rules:
    - Order must be IN_PROGRESS
    - User must be the assigned technician OR admin/staff
    """
    if user.company_id != order.company_id:
        return False

    if order.status != Order.Status.IN_PROGRESS:
        return False

    # Admin/staff can always complete
    if user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
        return True

    # Technician can only complete their own orders
    if user.role == UserRole.TECHNICIAN:
        technician = getattr(user, "technician_profile", None)
        if technician and order.technician_id == technician.id:
            return True

    return False


def can_cancel_order(*, user: CompanyUser, order: Order) -> bool:
    """
    Check if user can cancel or request cancellation of an order.

    Rules:
    - User must belong to same company
    - Order must not be in a terminal status
    - Admin can force cancel any non-terminal order
    - Technician/Customer can request cancellation
    """
    if user.company_id != order.company_id:
        return False

    terminal = [Order.Status.DONE, Order.Status.CANCELLED]
    if order.status in terminal:
        return False

    # Admin can always cancel
    if user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
        return True

    # Technician can request cancel for their assigned orders
    if user.role == UserRole.TECHNICIAN:
        technician = getattr(user, "technician_profile", None)
        return technician is not None and order.technician_id == technician.id

    # Customer can request cancel for their orders
    if user.role == UserRole.CUSTOMER:
        customer = getattr(user, "customer_profile", None)
        return customer is not None and order.customer_id == customer.id

    return False
