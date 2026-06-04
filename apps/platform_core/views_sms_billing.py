"""
Platform Core - SMS Billing Views.

Platform Owner views for managing SMS credit wallets, pricing, invoices.
All views require PLATFORM_OWNER role.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.permissions import require_platform_owner
from apps.tenants.models import Company

from .models import CompanySMSTransaction, CompanySMSWallet, GlobalSMSPricingSetting, PlatformBillingInvoice
from .services_sms_credit import SMSCreditService


@require_platform_owner
def sms_billing_index(request: HttpRequest) -> HttpResponse:
    """SMS billing dashboard — shows unpaid invoices summary + links."""
    unpaid_invoices = PlatformBillingInvoice.objects.filter(
        status=PlatformBillingInvoice.Status.UNPAID
    ).select_related("company").order_by("-created_at")[:20]
    unpaid_count = PlatformBillingInvoice.objects.filter(
        status=PlatformBillingInvoice.Status.UNPAID
    ).count()
    total_unpaid_amount = sum(inv.amount_rial for inv in unpaid_invoices)

    return render(request, "platform_core/sms_billing/index.html", {
        "unpaid_invoices": unpaid_invoices,
        "unpaid_count": unpaid_count,
        "total_unpaid_amount": total_unpaid_amount,
    })


@require_platform_owner
def sms_billing_settings(request: HttpRequest) -> HttpResponse:
    """GET/POST for GlobalSMSPricingSetting."""
    pricing = SMSCreditService.get_pricing()
    errors = {}
    success = False

    if request.method == "POST":
        try:
            characters_per_sms = int(request.POST.get("characters_per_sms", 60))
            price_per_sms_rial = int(request.POST.get("price_per_sms_rial", 520))
        except (ValueError, TypeError):
            errors["general"] = "مقادیر وارد شده معتبر نیست."
            return render(request, "platform_core/sms_billing/settings.html", {
                "pricing": pricing, "errors": errors, "success": success,
            })

        if characters_per_sms < 1:
            errors["characters_per_sms"] = "تعداد کاراکتر باید حداقل ۱ باشد."
        if price_per_sms_rial < 0:
            errors["price_per_sms_rial"] = "قیمت نمی‌تواند منفی باشد."

        if not errors:
            pricing.characters_per_sms = characters_per_sms
            pricing.price_per_sms_rial = price_per_sms_rial
            pricing.updated_by = request.user
            pricing.save(update_fields=["characters_per_sms", "price_per_sms_rial", "updated_by", "updated_at"])
            success = True

    return render(request, "platform_core/sms_billing/settings.html", {
        "pricing": pricing, "errors": errors, "success": success,
    })


@require_platform_owner
def sms_billing_companies(request: HttpRequest) -> HttpResponse:
    """List all companies with their SMS wallet balances."""
    companies = Company.objects.filter(is_active=True).order_by("name")
    company_data = []
    for company in companies:
        wallet = SMSCreditService.get_or_create_wallet(company)
        remaining_sms = SMSCreditService.get_remaining_sms_count(company)
        company_data.append({
            "company": company,
            "wallet": wallet,
            "remaining_sms": remaining_sms,
        })
    return render(request, "platform_core/sms_billing/companies.html", {
        "company_data": company_data,
    })


@require_platform_owner
def sms_billing_transactions(request: HttpRequest) -> HttpResponse:
    """List all SMS transactions."""
    transactions = CompanySMSTransaction.objects.select_related("company", "wallet").all()[:100]
    return render(request, "platform_core/sms_billing/transactions.html", {
        "transactions": transactions,
    })


@require_platform_owner
def sms_billing_invoices(request: HttpRequest) -> HttpResponse:
    """List all platform billing invoices with optional filters."""
    queryset = PlatformBillingInvoice.objects.select_related("company").all()

    # Apply filters
    status_filter = request.GET.get("status", "")
    company_filter = request.GET.get("company", "")
    type_filter = request.GET.get("type", "")

    if status_filter:
        queryset = queryset.filter(status=status_filter)
    if company_filter:
        queryset = queryset.filter(company_id=company_filter)
    if type_filter:
        queryset = queryset.filter(invoice_type=type_filter)

    invoices = queryset[:100]
    companies = Company.objects.filter(is_active=True).order_by("name")

    return render(request, "platform_core/sms_billing/invoices.html", {
        "invoices": invoices,
        "companies": companies,
        "status_filter": status_filter,
        "company_filter": company_filter,
        "type_filter": type_filter,
    })


@require_platform_owner
def sms_billing_invoice_detail(request: HttpRequest, invoice_id: int) -> HttpResponse:
    """Single invoice detail."""
    invoice = get_object_or_404(PlatformBillingInvoice, id=invoice_id)
    return render(request, "platform_core/sms_billing/invoice_detail.html", {
        "invoice": invoice,
    })


@require_platform_owner
def sms_billing_invoice_mark_paid(request: HttpRequest, invoice_id: int) -> HttpResponse:
    """POST to mark invoice as paid."""
    invoice = get_object_or_404(PlatformBillingInvoice, id=invoice_id)
    if request.method == "POST":
        SMSCreditService.mark_invoice_paid(invoice, paid_by=request.user)
    return redirect("platform_core:sms_billing_invoice_detail", invoice_id=invoice.id)
