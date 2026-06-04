"""
Common - Permission Helpers.

Reusable permission checks for tenant-scoped access control.
"""
from functools import wraps
from typing import Any, Callable

from django.http import Http404, HttpRequest, HttpResponseForbidden


def require_tenant(view_func: Callable) -> Callable:
    """
    Decorator: Ensures request has a resolved tenant (company).
    Returns 404 if no company is attached to the request.
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any):
        if not getattr(request, "company", None):
            raise Http404("Company not found.")
        return view_func(request, *args, **kwargs)

    return wrapper


def require_role(*allowed_roles: str) -> Callable:
    """
    Decorator: Ensures user has one of the allowed roles.

    Usage:
        @require_role("COMPANY_ADMIN", "COMPANY_STAFF")
        def manage_orders(request):
            ...
    """

    def decorator(view_func: Callable) -> Callable:
        @wraps(view_func)
        def wrapper(request: HttpRequest, *args: Any, **kwargs: Any):
            if not request.user.is_authenticated:
                return HttpResponseForbidden("Authentication required.")
            user_role = getattr(request.user, "role", None)
            if user_role not in allowed_roles:
                return HttpResponseForbidden("شما اجازه دسترسی به این بخش را ندارید. اگر فکر می‌کنید اشتباه است، از مدیر شرکت بخواهید دسترسی شما را فعال کند.")
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def require_company_membership(view_func: Callable) -> Callable:
    """
    Decorator: Ensures the authenticated user belongs to the current company.
    Prevents cross-tenant data access.
    """

    @wraps(view_func)
    def wrapper(request: HttpRequest, *args: Any, **kwargs: Any):
        if not request.user.is_authenticated:
            return HttpResponseForbidden("Authentication required.")

        company = getattr(request, "company", None)
        if not company:
            raise Http404("Company not found.")

        user_company_id = getattr(request.user, "company_id", None)
        if user_company_id != company.id:
            return HttpResponseForbidden("Access denied.")

        return view_func(request, *args, **kwargs)

    return wrapper
