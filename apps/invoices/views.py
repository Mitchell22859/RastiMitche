"""
Invoices - Views.

Thin views for invoice display and payment.
Business logic delegated to services/selectors.
"""
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render

from apps.accounts.models import UserRole
from apps.accounts.permissions import require_tenant_auth

from .models import Invoice
from .selectors import InvoiceSelector


@require_tenant_auth
def invoice_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    List invoices based on user role.
    - Admin/Staff: all company invoices
    - Customer: own invoices only
    """
    user = request.user
    company = request.company

    if user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
        invoices = InvoiceSelector.get_for_company(company=company)
    elif user.role == UserRole.CUSTOMER:
        customer = getattr(user, "customer_profile", None)
        if customer:
            invoices = InvoiceSelector.get_for_customer(customer=customer)
        else:
            invoices = Invoice.objects.none()
    else:
        invoices = Invoice.objects.none()

    return render(request, "invoices/list.html", {
        "invoices": invoices,
        "company": company,
    })


@require_tenant_auth
def invoice_detail(request: HttpRequest, invoice_id: int, **kwargs) -> HttpResponse:
    """View a single invoice."""
    company = request.company
    invoice = InvoiceSelector.get_by_id_for_company(
        invoice_id=invoice_id, company=company
    )

    if invoice is None:
        raise Http404("Invoice not found.")

    user = request.user
    if user.role == UserRole.CUSTOMER:
        customer = getattr(user, "customer_profile", None)
        if not customer or invoice.customer_id != customer.id:
            return HttpResponseForbidden("Access denied.")

    from apps.invoices.services_wage import calculate_technician_wage

    return render(request, "invoices/detail.html", {
        "invoice": invoice,
        "company": company,
        "wage_data": calculate_technician_wage(invoice),
    })


def public_invoice_detail(request: HttpRequest, public_code: str, **kwargs) -> HttpResponse:
    """Read-only public invoice view by short public code."""
    company = request.company
    invoice = InvoiceSelector.get_by_public_code_for_company(
        company=company, public_code=public_code,
    )
    if invoice is None:
        raise Http404("Invoice not found.")
    if invoice.status == Invoice.Status.CANCELLED:
        raise Http404("Invoice not found.")
    return render(request, "invoices/public_detail.html", {
        "invoice": invoice,
        "company": company,
        "public_pay_url": f"/{company.code}/invoices/{invoice.id}/pay/",
    })


def invoice_print(request: HttpRequest, public_code: str, **kwargs) -> HttpResponse:
    """
    Invoice print/download page (Phase 27A) — public access via public_code.

    Renders a clean, print-optimized HTML page for the invoice.
    Browser print dialog or "Save as PDF" produces a production-quality document.

    Uses the invoice public_code (not numeric ID) in the URL for safety.

    Access rules match public_invoice_detail:
    - Anyone with the public_code link can view (same as public detail).
    - DRAFT and CANCELLED invoices are not available.
    """
    company = request.company
    invoice = InvoiceSelector.get_by_public_code_for_company(
        company=company, public_code=public_code,
    )

    if invoice is None:
        raise Http404("Invoice not found.")

    # Block CANCELLED invoices only (consistent with public_invoice_detail)
    if invoice.status == Invoice.Status.CANCELLED:
        raise Http404("Invoice not found.")

    return render(request, "invoices/print.html", {
        "invoice": invoice,
        "company": company,
    })


def invoice_pay(request: HttpRequest, invoice_id: int, **kwargs) -> HttpResponse:
    """Public checkout page for an issued invoice.

    This endpoint intentionally does not require login: anyone with the
    invoice link may pay on behalf of the customer. Tenant isolation is kept by
    the company-prefixed URL and company-scoped invoice lookup.
    """
    from django.contrib import messages
    from django.utils import timezone
    from apps.payments.models import Payment
    from apps.payments.selectors import PaymentGatewaySelector

    company = request.company
    invoice = InvoiceSelector.get_by_id_for_company(invoice_id=invoice_id, company=company)

    if invoice is None:
        raise Http404("Invoice not found.")

    if not invoice.is_payable:
        return render(request, "payments/invoice_checkout.html", {
            "invoice": invoice,
            "company": company,
            "payment_reference": "-",
            "has_gateway": False,
            "public_invoice_url": f"/i/{invoice.public_code}/" if invoice.public_code else f"/{company.code}/invoices/public/{invoice.public_code}/",
        })

    payment = (
        Payment.objects
        .filter(company=company, invoice=invoice, status__in=[Payment.Status.INITIATED, Payment.Status.PENDING])
        .order_by("-created_at")
        .first()
    )

    if payment is None:
        payment = Payment.objects.create(
            company=company,
            invoice=invoice,
            gateway=None,
            amount=invoice.total_amount,
            status=Payment.Status.INITIATED,
            reference_id=f"PAY-{company.code.upper()}-{invoice.id:05d}-{timezone.now().strftime('%H%M%S')}",
            metadata={
                "method": "online",
                "stage": "checkout_created",
                "note": "Internal tracking record before gateway connection.",
            },
        )

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "apply_discount":
            from apps.reports.discount_services import DiscountCodeService

            if invoice.campaign_discount_amount and invoice.campaign_discount_amount > 0 or getattr(invoice, "discount_code", None):
                messages.error(request, "کد تخفیف قبلاً اعمال شده است.")
                return redirect(f"/{company.code}/invoices/{invoice.id}/pay/")

            ok, message, _amount = DiscountCodeService.apply_to_invoice(
                company=company,
                invoice=invoice,
                raw_code=request.POST.get("discount_code", ""),
            )
            if ok:
                messages.success(request, message)
            else:
                messages.error(request, message)

            invoice.refresh_from_db()
            payment.amount = invoice.total_amount
            payment.metadata = {
                **(payment.metadata or {}),
                "last_discount_apply_ok": ok,
                "last_discount_apply_message": message,
            }
            payment.save(update_fields=["amount", "metadata", "updated_at"])
            return redirect(f"/{company.code}/invoices/{invoice.id}/pay/")

        if action == "start_gateway":
            from apps.payments.services import PaymentStartService

            gateway = PaymentGatewaySelector.get_default_for_company(company=company)
            if gateway is None:
                messages.error(request, "درگاه پرداخت هنوز برای این شرکت تنظیم نشده است.")
                return redirect(f"/{company.code}/invoices/{invoice.id}/pay/")

            callback_url = request.build_absolute_uri(f"/{company.code}/payments/callback/")

            try:
                _gateway_payment, _attempt, redirect_url = PaymentStartService.start(
                    invoice=invoice,
                    callback_url=callback_url,
                    gateway=gateway,
                )
            except ValueError as exc:
                messages.error(request, str(exc))
                return redirect(f"/{company.code}/invoices/{invoice.id}/pay/")

            if redirect_url:
                return redirect(redirect_url)

            messages.error(request, "اتصال به درگاه ناموفق بود. لطفاً دوباره تلاش کنید.")
            return redirect(f"/{company.code}/invoices/{invoice.id}/pay/")

    gateway = PaymentGatewaySelector.get_default_for_company(company=company)

    return render(request, "payments/invoice_checkout.html", {
        "invoice": invoice,
        "company": company,
        "payment": payment,
        "payment_reference": payment.reference_id or f"PAY-{company.code.upper()}-{invoice.id:05d}",
        "has_gateway": gateway is not None,
        "public_invoice_url": f"/i/{invoice.public_code}/" if invoice.public_code else f"/{company.code}/invoices/public/{invoice.public_code}/",
    })

# =============================================================================
# DISCOUNT CODE APPLY
# =============================================================================

def _invoice_discount_redirect(request, invoice, *, public: bool, success: bool, message: str):
    from django.contrib import messages
    from django.shortcuts import redirect

    if success:
        messages.success(request, message)
    else:
        messages.error(request, message)

    if public:
        return redirect(f"/i/{invoice.public_code}/")
    return redirect(f"/{invoice.company.code}/invoices/{invoice.id}/")


@require_tenant_auth
def invoice_apply_discount(request: HttpRequest, invoice_id: int, **kwargs) -> HttpResponse:
    from django.http import HttpResponseForbidden
    from apps.reports.discount_services import DiscountCodeService

    if request.method != "POST":
        return HttpResponseForbidden("POST only.")

    company = request.company
    invoice = InvoiceSelector.get_by_id_for_company(invoice_id=invoice_id, company=company)
    if invoice is None:
        raise Http404("Invoice not found.")

    ok, message, _amount = DiscountCodeService.apply_to_invoice(
        company=company,
        invoice=invoice,
        raw_code=request.POST.get("discount_code", ""),
    )
    return _invoice_discount_redirect(request, invoice, public=False, success=ok, message=message)


def public_invoice_apply_discount(request: HttpRequest, public_code: str, **kwargs) -> HttpResponse:
    from django.http import HttpResponseForbidden
    from apps.reports.discount_services import DiscountCodeService

    if request.method != "POST":
        return HttpResponseForbidden("POST only.")

    company = request.company
    invoice = InvoiceSelector.get_by_public_code_for_company(company=company, public_code=public_code)
    if invoice is None:
        raise Http404("Invoice not found.")

    ok, message, _amount = DiscountCodeService.apply_to_invoice(
        company=company,
        invoice=invoice,
        raw_code=request.POST.get("discount_code", ""),
    )
    return _invoice_discount_redirect(request, invoice, public=True, success=ok, message=message)
