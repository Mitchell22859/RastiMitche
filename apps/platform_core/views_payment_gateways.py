"""Platform Owner - Payment Gateway Settings Views."""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from apps.accounts.permissions import require_platform_owner
from .models import PlatformPaymentGatewaySetting, PaymentGatewayProvider
from .services_payment_gateway import PaymentGatewayResolver


@require_platform_owner
def platform_gateway_index(request: HttpRequest) -> HttpResponse:
    return redirect("platform_core:platform_gateway_settings")


@require_platform_owner
def platform_gateway_settings(request: HttpRequest) -> HttpResponse:
    gateway = PaymentGatewayResolver.get_platform_gateway()
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

    return render(request, "platform_core/payment_gateways/settings.html", {
        "gateway": gateway,
        "providers": PaymentGatewayProvider.choices,
        "success": success,
    })


@require_platform_owner
def platform_gateway_test(request: HttpRequest) -> HttpResponse:
    gateway = PaymentGatewayResolver.get_platform_gateway()
    result = {"status": "mock", "message": "اتصال آزمایشی — درگاه واقعی متصل نیست."}
    return render(request, "platform_core/payment_gateways/test.html", {
        "gateway": gateway, "result": result,
    })
