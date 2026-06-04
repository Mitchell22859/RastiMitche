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

    if request.method == "POST":
        gateway.provider = request.POST.get("provider", "MOCK")
        gateway.is_active = request.POST.get("is_active") == "on"
        new_merchant = request.POST.get("merchant_id", "").strip()
        if new_merchant and new_merchant != gateway.merchant_id_masked:
            gateway.merchant_id = new_merchant
        gateway.terminal_id = request.POST.get("terminal_id", "").strip()
        gateway.callback_base_url = request.POST.get("callback_base_url", "").strip()
        gateway.sandbox_mode = request.POST.get("sandbox_mode") == "on"
        gateway.description = request.POST.get("description", "").strip()
        gateway.updated_by = request.user
        gateway.save()
        success = True

    return render(request, "tenants/admin_payment_gateway.html", {
        "company": company,
        "gateway": gateway,
        "providers": PaymentGatewayProvider.choices,
        "success": success,
    })


@require_tenant_role("COMPANY_ADMIN")
def tenant_gateway_test(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    gateway = PaymentGatewayResolver.get_company_gateway(company)
    result = {"status": "mock", "message": "اتصال آزمایشی — درگاه واقعی متصل نیست."}
    return render(request, "tenants/admin_payment_gateway_test.html", {
        "company": company, "gateway": gateway, "result": result,
    })
