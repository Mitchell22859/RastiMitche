"""
Tenants - Legacy URL Redirect Views (Phase 24).

These views handle old/bookmarked URLs that previously exposed admin or
technician actions at the public level (/<company_code>/orders/,
/<company_code>/reports/, /<company_code>/notifications/).

Behavior:
- Anonymous users → redirect to tenant login.
- Admin/Operator → redirect to admin panel equivalent.
- Technician → redirect to technician panel equivalent.
- Customer → redirect to customer dashboard (or 404 for irrelevant pages).
- Any attempt to use action URLs (accept, complete, cancel, create) returns 404.

IMPORTANT: No order/report/notification actions are accessible from these paths.
"""
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseRedirect

from apps.accounts.models import UserRole


def _get_company_code(request: HttpRequest) -> str:
    """Helper to get company code from request."""
    return request.company.code


def _login_redirect(request: HttpRequest) -> HttpResponseRedirect:
    """Redirect to tenant login."""
    return HttpResponseRedirect(f"/{_get_company_code(request)}/login/")


def legacy_orders_redirect(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Handle /<company_code>/orders/ legacy path.

    Redirects authenticated users to their role-specific order panel.
    Anonymous users are sent to login.
    """
    company = getattr(request, "company", None)
    if not company:
        raise Http404()

    if not request.user.is_authenticated:
        return _login_redirect(request)

    code = company.code
    role = getattr(request.user, "role", None)

    if role in (UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF):
        return HttpResponseRedirect(f"/{code}/admin/orders/")
    elif role == UserRole.TECHNICIAN:
        return HttpResponseRedirect(f"/{code}/tech/orders/my/")
    elif role == UserRole.CUSTOMER:
        return HttpResponseRedirect(f"/{code}/customer/")
    else:
        return _login_redirect(request)


def legacy_orders_catch_all(request: HttpRequest, subpath: str = "", **kwargs) -> HttpResponse:
    """
    Handle /<company_code>/orders/<anything> legacy paths.

    Old URLs like /orders/123/, /orders/123/accept/, /orders/create/ are
    no longer served here. We redirect to the correct panel or return 404.
    """
    company = getattr(request, "company", None)
    if not company:
        raise Http404()

    if not request.user.is_authenticated:
        return _login_redirect(request)

    code = company.code
    role = getattr(request.user, "role", None)

    # LEGACY_TECH_ORDER_LIST_REDIRECTS
    # Old technician list URLs from the previous UI:
    # /<company_code>/orders/available/ and /<company_code>/orders/my/
    # must redirect to the Phase 24 technician namespace.
    normalized_subpath = subpath.strip("/")

    if normalized_subpath == "available":
        if role == UserRole.TECHNICIAN:
            return HttpResponseRedirect(f"/{code}/tech/orders/available/")
        if role in (UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF):
            return HttpResponseRedirect(f"/{code}/admin/orders/")
        raise Http404()

    if normalized_subpath == "my":
        if role == UserRole.TECHNICIAN:
            return HttpResponseRedirect(f"/{code}/tech/orders/my/")
        if role in (UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF):
            return HttpResponseRedirect(f"/{code}/admin/orders/")
        raise Http404()
    # Special case: /orders/create/ → only admin/operator should be redirected
    if subpath.rstrip("/") == "create":
        if role in (UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF):
            return HttpResponseRedirect(f"/{code}/admin/orders/create/")
        raise Http404()

    # Try to extract an order ID for redirect
    parts = subpath.strip("/").split("/")
    if parts and parts[0].isdigit():
        order_id = parts[0]
        # If there's a sub-action (accept, complete, cancel, status, etc.) → 404
        # These actions must only be accessed through /tech/ or /admin/ paths.
        if len(parts) > 1:
            raise Http404()
        # Redirect to detail in the appropriate panel
        if role in (UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF):
            return HttpResponseRedirect(f"/{code}/admin/orders/{order_id}/")
        elif role == UserRole.TECHNICIAN:
            return HttpResponseRedirect(f"/{code}/tech/orders/{order_id}/")
        # Customers cannot view individual orders via this legacy path
        raise Http404()

    # Anything else → 404
    raise Http404()


def legacy_reports_redirect(request: HttpRequest, subpath: str = "", **kwargs) -> HttpResponse:
    """
    Handle /<company_code>/reports/ legacy path.

    Reports are admin-only. Redirects admin/operator to admin reports.
    All other roles get 404 (reports are not public/customer-facing).
    """
    company = getattr(request, "company", None)
    if not company:
        raise Http404()

    if not request.user.is_authenticated:
        return _login_redirect(request)

    code = company.code
    role = getattr(request.user, "role", None)

    if role in (UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF):
        return HttpResponseRedirect(f"/{code}/admin/reports/")

    raise Http404()


def legacy_notifications_redirect(request: HttpRequest, subpath: str = "", **kwargs) -> HttpResponse:
    """
    Handle /<company_code>/notifications/ legacy path.

    Redirects to the role-specific notification panel.
    """
    company = getattr(request, "company", None)
    if not company:
        raise Http404()

    if not request.user.is_authenticated:
        return _login_redirect(request)

    code = company.code
    role = getattr(request.user, "role", None)

    if role in (UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF):
        return HttpResponseRedirect(f"/{code}/admin/notifications/")
    elif role == UserRole.TECHNICIAN:
        return HttpResponseRedirect(f"/{code}/tech/notifications/")

    # Customers don't have a dedicated notifications page currently
    raise Http404()

