"""Tenant Company - Payment Gateway Settings Views."""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from apps.accounts.permissions import require_tenant_role
from .models import CompanyPaymentGatewaySetting, PaymentGatewayProvider
from .services_payment_gateway import PaymentGatewayResolver


@require_tenant_role("COMPANY_ADMIN")
def tenant_gateway_settings(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    gateway = PaymentGatewayResolver.get_company_gateway(company)
    success = False

    error = ""

    if request.method == "POST":
        wants_active = request.POST.get("is_active") == "on"

        # Enforce KYC eligibility before allowing gateway activation
        if wants_active:
            try:
                from apps.tenants.services_merchant_profile import CompanyPaymentEligibilityService
                eligible, reason = CompanyPaymentEligibilityService.is_gateway_enabled(company)
            except Exception:
                eligible, reason = False, "eligibility_check_failed"

            if not eligible:
                error = "امکان فعال‌سازی درگاه وجود ندارد. ابتدا اطلاعات ثبتی و بانکی شرکت باید توسط پلتفرم تأیید شود."
                wants_active = False

        gateway.provider = request.POST.get("provider", "MOCK")
        gateway.is_active = wants_active
        new_merchant = request.POST.get("merchant_id", "").strip()
        if new_merchant and new_merchant != gateway.merchant_id_masked:
            gateway.merchant_id = new_merchant
        gateway.terminal_id = request.POST.get("terminal_id", "").strip()
        gateway.callback_base_url = request.POST.get("callback_base_url", "").strip()
        gateway.sandbox_mode = request.POST.get("sandbox_mode") == "on"
        gateway.description = request.POST.get("description", "").strip()
        gateway.updated_by = request.user
        gateway.save()
        if not error:
            success = True

    try:
        from apps.tenants.services_merchant_profile import CompanyPaymentEligibilityService
        gateway_eligible, gateway_eligible_reason = CompanyPaymentEligibilityService.is_gateway_enabled(company)
    except Exception:
        gateway_eligible, gateway_eligible_reason = True, ""

    return render(request, "tenants/admin_payment_gateway.html", {
        "company": company,
        "gateway": gateway,
        "providers": PaymentGatewayProvider.choices,
        "success": success,
        "error": error,
        "gateway_eligible": gateway_eligible,
        "gateway_eligible_reason": gateway_eligible_reason,
    })


@require_tenant_role("COMPANY_ADMIN")
def tenant_gateway_test(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    gateway = PaymentGatewayResolver.get_company_gateway(company)
    result = {"status": "mock", "message": "اتصال آزمایشی — درگاه واقعی متصل نیست."}
    return render(request, "tenants/admin_payment_gateway_test.html", {
        "company": company, "gateway": gateway, "result": result,
    })
