"""
Payments - Views.

Thin views for payment callbacks and results.
Business logic delegated to services.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.accounts.permissions import require_tenant_auth

from .services import PaymentCallbackService


def payment_callback(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Payment gateway callback endpoint.

    This is called by the gateway after payment attempt.
    Handles both success and failure cases.
    """
    company = getattr(request, "company", None)
    if not company:
        return render(request, "payments/result.html", {
            "success": False,
            "message": "Invalid callback.",
            "company": None,
        })

    # Gateway sends reference_id back (via GET or POST)
    reference_id = (
        request.GET.get("Authority")
        or request.GET.get("reference_id")
        or request.POST.get("reference_id")
        or request.GET.get("id")
        or ""
    )

    if not reference_id:
        return render(request, "payments/result.html", {
            "success": False,
            "message": "No payment reference received.",
            "company": company,
        })

    success, message, payment = PaymentCallbackService.handle_callback(
        company=company,
        reference_id=reference_id,
    )

    return render(request, "payments/result.html", {
        "success": success,
        "message": message,
        "payment": payment,
        "company": company,
    })


@require_tenant_auth
def payment_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """List payments for the company (admin view)."""
    from .selectors import PaymentSelector

    company = request.company
    payments = PaymentSelector.get_for_company(company=company)

    return render(request, "payments/list.html", {
        "payments": payments,
        "company": company,
    })
