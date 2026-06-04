"""Recipient resolution for notification events."""
from __future__ import annotations


def _clean_phone(value: str | None) -> str:
    return (value or "").strip()


def get_user_phone(user) -> str:
    if not user:
        return ""
    return _clean_phone(
        getattr(user, "phone", "")
        or getattr(user, "mobile", "")
        or getattr(user, "phone_number", "")
    )


def get_company_admin_recipients(company) -> list[dict]:
    if company is None:
        return []

    try:
        from apps.accounts.models import CompanyUser, UserRole
    except Exception:
        return []

    admins = CompanyUser.objects.filter(
        company=company,
        role=UserRole.COMPANY_ADMIN,
        is_active=True,
    ).order_by("id")

    recipients = []
    for user in admins:
        phone = get_user_phone(user)
        if phone:
            recipients.append({"phone": phone, "user": user, "label": getattr(user, "username", "") or "admin"})
    return recipients


def get_platform_owner_recipients() -> list[dict]:
    """Return platform-owner users for platform-level audit/admin events."""
    try:
        from apps.accounts.models import CompanyUser, UserRole
    except Exception:
        return []

    users = CompanyUser.objects.filter(
        role=UserRole.PLATFORM_OWNER,
        is_active=True,
    ).order_by("id")

    result = []
    for user in users:
        phone = get_user_phone(user)
        if phone:
            result.append({"phone": phone, "user": user, "label": getattr(user, "username", "") or "platform_owner"})
    return result


def get_direct_user_recipient(user) -> list[dict]:
    """Return a recipient list for events whose target is directly a CompanyUser."""
    phone = get_user_phone(user)
    label = getattr(user, "username", "") or getattr(user, "first_name", "") or "user"
    return [{"phone": phone, "user": user, "label": label}] if phone else []


def get_invoice_customer_recipient(invoice) -> list[dict]:
    order = getattr(invoice, "order", None)
    phone = (
        getattr(invoice, "customer_phone_snapshot", "")
        or getattr(order, "customer_phone", "")
        or getattr(order, "display_customer_phone", "")
        or ""
    )
    name = (
        getattr(invoice, "customer_name_snapshot", "")
        or getattr(order, "customer_name", "")
        or getattr(order, "display_customer_name", "")
        or ""
    )
    phone = _clean_phone(phone)
    return [{"phone": phone, "label": name or "customer"}] if phone else []


def get_order_customer_recipient(order) -> list[dict]:
    phone = _clean_phone(getattr(order, "customer_phone", "") or getattr(order, "display_customer_phone", "") or "")
    name = getattr(order, "customer_name", "") or getattr(order, "display_customer_name", "") or ""
    return [{"phone": phone, "label": name or "customer"}] if phone else []


def get_order_technician_recipient(order) -> list[dict]:
    technician = getattr(order, "technician", None)
    return get_technician_profile_recipient(technician)


def get_technician_profile_recipient(technician) -> list[dict]:
    user = getattr(technician, "user", None)
    phone = get_user_phone(user)
    label = getattr(user, "username", "") if user else "technician"
    return [{"phone": phone, "user": user, "label": label}] if phone else []


def get_available_technician_recipients(order) -> list[dict]:
    # Return only technicians who can actually see this order.
    company = getattr(order, "company", None)
    if company is None:
        return []

    try:
        from apps.accounts.models import Technician
        from apps.orders.selectors import TechnicianOrderVisibilitySelector
    except Exception:
        return []

    technicians = Technician.objects.filter(company=company, is_available=True).select_related("user")
    result = []

    for technician in technicians:
        try:
            visible = TechnicianOrderVisibilitySelector.get_available_orders(
                technician=technician,
            ).filter(id=getattr(order, "id", None)).exists()
        except Exception:
            visible = False

        if not visible:
            continue

        phone = get_user_phone(getattr(technician, "user", None))
        if phone:
            result.append({
                "phone": phone,
                "user": technician.user,
                "label": getattr(technician.user, "username", "") or "technician",
            })

    return result
