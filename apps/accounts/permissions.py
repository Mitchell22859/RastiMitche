"""
Accounts - Permissions.

ALL access control logic is centralized here.
Views must use these helpers — no inline permission logic in views.

Provides:
- Role checking functions
- Decorators for view protection
- Tenant isolation enforcement
"""
from functools import wraps
from typing import Any, Callable

from django.http import Http404, HttpRequest, HttpResponseForbidden, HttpResponseRedirect

from .models import UserRole


# =============================================================================
# ROLE CHECK FUNCTIONS
# =============================================================================


def is_platform_owner(user) -> bool:
    """Check if user is a platform owner."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role", None) == UserRole.PLATFORM_OWNER


def is_company_admin(user) -> bool:
    """Check if user is a company admin."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role", None) == UserRole.COMPANY_ADMIN


def is_company_staff_or_admin(user) -> bool:
    """Check if user is company staff or admin."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role", None) in [
        UserRole.COMPANY_ADMIN,
        UserRole.COMPANY_STAFF,
    ]


def is_technician(user) -> bool:
    """Check if user is a technician."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role", None) == UserRole.TECHNICIAN


def is_customer(user) -> bool:
    """Check if user is a customer."""
    if not user or not user.is_authenticated:
        return False
    return getattr(user, "role", None) == UserRole.CUSTOMER


def user_belongs_to_company(user, company) -> bool:
    """Check if user belongs to the given company."""
    if not user or not user.is_authenticated:
        return False
    if company is None:
        return False
    return getattr(user, "company_id", None) == company.id


# =============================================================================
# VIEW DECORATORS
# =============================================================================


def require_platform_owner(view_func: Callable) -> Callable:
    """
    Decorator: Restrict view to PLATFORM_OWNER role only.
    Redirects unauthenticated users to /login/.
    Returns 403 for authenticated non-platform-owners.
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any):
        if not request.user.is_authenticated:
            return HttpResponseRedirect("/login/")
        if not is_platform_owner(request.user):
            return HttpResponseForbidden("Platform owners only.")
        return view_func(request, *args, **kwargs)

    return wrapper


def require_tenant_auth(view_func: Callable) -> Callable:
    """
    Decorator: Ensures user is authenticated AND belongs to the current tenant.
    Redirects to tenant login if not authenticated.
    Returns 403 if user doesn't belong to this company.
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any):
        company = getattr(request, "company", None)
        if not company:
            raise Http404("Company not found.")

        if not request.user.is_authenticated:
            return HttpResponseRedirect(f"/login/")

        if not user_belongs_to_company(request.user, company):
            return HttpResponseForbidden("Access denied.")

        return view_func(request, *args, **kwargs)

    return wrapper


def require_tenant_role(*allowed_roles: str) -> Callable:
    """
    Decorator: Ensures user is authenticated, belongs to tenant, and has role.

    Usage:
        @require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
        def manage_orders(request):
            ...
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any):
            company = getattr(request, "company", None)
            if not company:
                raise Http404("Company not found.")

            if not request.user.is_authenticated:
                return HttpResponseRedirect("/login/")

            if not user_belongs_to_company(request.user, company):
                return HttpResponseForbidden("Access denied.")

            user_role = getattr(request.user, "role", None)
            if user_role not in allowed_roles:
                return HttpResponseForbidden("شما اجازه دسترسی به این بخش را ندارید. اگر فکر می‌کنید اشتباه است، از مدیر شرکت بخواهید دسترسی شما را فعال کند.")

            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator
