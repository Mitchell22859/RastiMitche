"""
Invoices - Short Public Invoice View.

Handles /i/<public_code>/ — a globally-accessible short link for invoices.

Tenant isolation note:
    Invoice.public_code has unique=True at the database level, so there is
    no risk of collision between companies. A single query by public_code
    will always return at most one invoice from one specific company.

Access rules:
    - No authentication required.
    - CANCELLED invoices return 404.
    - DRAFT invoices return 404 (only ISSUED and PAID are publicly visible).
    - The company context is resolved FROM the invoice (not from the URL).
"""
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from .models import Invoice


def short_public_invoice_detail(request: HttpRequest, public_code: str) -> HttpResponse:
    """
    Read-only public invoice view accessed via /i/<public_code>/.

    Since public_code is globally unique (DB constraint), we query without
    company filtering. The invoice's own company is passed to the template
    for branding/display purposes.
    """
    if not public_code:
        raise Http404("Invoice not found.")

    invoice = (
        Invoice.objects
        .select_related("company", "order", "customer")
        .prefetch_related("items")
        .filter(public_code=public_code)
        .first()
    )

    if invoice is None:
        raise Http404("Invoice not found.")

    # Hide cancelled and draft invoices from public access
    if invoice.status in (Invoice.Status.CANCELLED, Invoice.Status.DRAFT):
        raise Http404("Invoice not found.")

    # Resolve company from the invoice itself for template branding
    company = invoice.company

    return render(request, "invoices/public_detail.html", {
        "invoice": invoice,
        "company": company,
        "public_pay_url": f"/{company.code}/invoices/{invoice.id}/pay/",
    })
