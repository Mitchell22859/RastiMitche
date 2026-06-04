"""
Platform Core - Tenant SMS Credit Views.

Views for tenant company admins to view their SMS credit wallet,
request recharges, and view invoices/transactions.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import require_tenant_role

from .models import CompanySMSTransaction, PlatformBillingInvoice
from .services_sms_credit import SMSCreditService


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_sms_credit(request: HttpRequest, **kwargs) -> HttpResponse:
    """Overview: balance, remaining SMS, pricing info."""
    company = request.company
    wallet = SMSCreditService.get_or_create_wallet(company)
    pricing = SMSCreditService.get_pricing()
    remaining_sms = SMSCreditService.get_remaining_sms_count(company)

    return render(request, "tenants/admin_sms_credit.html", {
        "company": company,
        "wallet": wallet,
        "pricing": pricing,
        "remaining_sms": remaining_sms,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_sms_recharge(request: HttpRequest, **kwargs) -> HttpResponse:
    """GET shows form with quick amounts, POST creates invoice."""
    company = request.company
    quick_amounts = [50000, 100000, 200000, 500000, 1000000]
    errors = {}
    success = False

    if request.method == "POST":
        try:
            amount_rial = int(request.POST.get("amount_rial", 0))
        except (ValueError, TypeError):
            errors["amount_rial"] = "مبلغ وارد شده معتبر نیست."
            return render(request, "tenants/admin_sms_recharge.html", {
                "company": company, "quick_amounts": quick_amounts,
                "errors": errors, "success": success,
            })

        if amount_rial < 10000:
            errors["amount_rial"] = "حداقل مبلغ شارژ ۱۰,۰۰۰ ریال است."
        else:
            invoice = SMSCreditService.create_recharge_invoice(
                company=company, amount_rial=amount_rial, created_by=request.user,
            )
            success = True
            return render(request, "tenants/admin_sms_recharge.html", {
                "company": company, "quick_amounts": quick_amounts,
                "errors": errors, "success": success, "invoice": invoice,
            })

    return render(request, "tenants/admin_sms_recharge.html", {
        "company": company, "quick_amounts": quick_amounts,
        "errors": errors, "success": success,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_sms_transactions(request: HttpRequest, **kwargs) -> HttpResponse:
    """List wallet transactions for this company."""
    company = request.company
    transactions = CompanySMSTransaction.objects.filter(company=company).select_related("wallet")[:50]
    return render(request, "tenants/admin_sms_transactions.html", {
        "company": company,
        "transactions": transactions,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_sms_invoices(request: HttpRequest, **kwargs) -> HttpResponse:
    """List platform invoices for this company."""
    company = request.company
    invoices = PlatformBillingInvoice.objects.filter(company=company)[:50]
    return render(request, "tenants/admin_sms_invoices.html", {
        "company": company,
        "invoices": invoices,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def tenant_sms_invoice_detail(request: HttpRequest, invoice_id: int, **kwargs) -> HttpResponse:
    """Single invoice detail (no mark-paid button for tenants)."""
    company = request.company
    invoice = get_object_or_404(PlatformBillingInvoice, id=invoice_id, company=company)
    return render(request, "tenants/admin_sms_invoice_detail.html", {
        "company": company,
        "invoice": invoice,
    })
