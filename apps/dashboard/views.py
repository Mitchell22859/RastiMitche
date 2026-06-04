"""
Dashboard - Views.

Role-based dashboards. Each role sees only their own data.
All business logic is in selectors — views are thin.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.accounts.permissions import require_platform_owner, require_tenant_role

from .selectors import (
    CompanyDashboardSelector,
    CustomerDashboardSelector,
    PlatformDashboardSelector,
    TechnicianDashboardSelector,
)


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def dashboard_home(request: HttpRequest, **kwargs) -> HttpResponse:
    """Company admin/staff dashboard."""
    company = request.company
    stats = CompanyDashboardSelector.get_stats(company=company)
    recent_orders = CompanyDashboardSelector.get_recent_orders(company=company)

    return render(request, "dashboard/home.html", {
        "company": company,
        "stats": stats,
        "recent_orders": recent_orders,
    })


@require_tenant_role("TECHNICIAN")
def technician_home(request: HttpRequest, **kwargs) -> HttpResponse:
    """Technician dashboard."""
    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    stats = {}
    recent_orders = []
    if technician:
        stats = TechnicianDashboardSelector.get_stats(technician=technician)
        recent_orders = TechnicianDashboardSelector.get_recent_assigned(
            technician=technician
        )

    return render(request, "dashboard/technician_home.html", {
        "company": company,
        "stats": stats,
        "recent_orders": recent_orders,
    })


@require_tenant_role("CUSTOMER")
def customer_home(request: HttpRequest, **kwargs) -> HttpResponse:
    """Customer dashboard."""
    company = request.company
    customer = getattr(request.user, "customer_profile", None)

    stats = {}
    recent_orders = []
    if customer:
        stats = CustomerDashboardSelector.get_stats(customer=customer)
        recent_orders = CustomerDashboardSelector.get_recent_orders(customer=customer)

    return render(request, "dashboard/customer_home.html", {
        "company": company,
        "stats": stats,
        "recent_orders": recent_orders,
    })
