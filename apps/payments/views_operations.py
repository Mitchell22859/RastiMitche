"""
Payments - Operations Dashboard Views (P13).

Read-only operational views for payment health monitoring.
No mutations. No sensitive KYC/banking data displayed.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.accounts.permissions import require_platform_owner, require_tenant_role

from .selectors_operations import PaymentOperationsSelector


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def company_payment_operations(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Company admin payment operations dashboard.

    Shows gateway payment health for the current company only.
    No cross-tenant data. No mutation actions.
    """
    company = request.company
    health = PaymentOperationsSelector.get_company_payment_health(company)
    alert = PaymentOperationsSelector.get_company_alert_badge(company)

    return render(request, "payments/operations_company.html", {
        "company": company,
        "health": health,
        "alert": alert,
    })


@require_platform_owner
def platform_payment_operations(request: HttpRequest) -> HttpResponse:
    """
    Platform owner payment operations dashboard.

    Shows global gateway payment health across all companies.
    No mutation actions.
    """
    health = PaymentOperationsSelector.get_platform_payment_health()
    alert = PaymentOperationsSelector.get_platform_alert_badge()

    return render(request, "payments/operations_platform.html", {
        "health": health,
        "alert": alert,
    })
