"""Payment Gateway Resolver Service. No real API calls."""
from .models import PlatformPaymentGatewaySetting, CompanyPaymentGatewaySetting, PaymentGatewayProvider


class PaymentGatewayResolver:
    """
    Resolves which payment gateway to use for different contexts.
    
    Rules:
    - PlatformBillingInvoice (SMS recharge, subscription) → Platform gateway
    - Order/service invoices → Company gateway
    - No active gateway → MOCK fallback
    
    TODO (Future): Connect to real Zarinpal/Zibal/IDPay adapters
    """

    @staticmethod
    def get_platform_gateway():
        """Get platform owner's payment gateway setting."""
        setting = PlatformPaymentGatewaySetting.objects.first()
        if setting is None:
            setting = PlatformPaymentGatewaySetting.objects.create(
                provider=PaymentGatewayProvider.MOCK, is_active=False, sandbox_mode=True
            )
        return setting

    @staticmethod
    def get_company_gateway(company):
        """Get a company's payment gateway setting."""
        setting, _ = CompanyPaymentGatewaySetting.objects.get_or_create(
            company=company,
            defaults={"provider": PaymentGatewayProvider.MOCK, "is_active": False, "sandbox_mode": True}
        )
        return setting

    @staticmethod
    def get_gateway_for_platform_invoice(invoice):
        """Platform billing invoices use Platform gateway."""
        return PaymentGatewayResolver.get_platform_gateway()

    @staticmethod
    def get_gateway_for_order_invoice(invoice):
        """Order/service invoices use Company gateway."""
        return PaymentGatewayResolver.get_company_gateway(invoice.company)

    @staticmethod
    def is_platform_gateway_active():
        gw = PaymentGatewayResolver.get_platform_gateway()
        return gw.is_active and gw.provider != PaymentGatewayProvider.MOCK

    @staticmethod
    def is_company_gateway_active(company):
        gw = PaymentGatewayResolver.get_company_gateway(company)
        return gw.is_active and gw.provider != PaymentGatewayProvider.MOCK
