"""
Payments - Provider Registry.

Maps gateway types to provider implementations.
Central place to register new payment providers.
"""
from typing import Optional

from apps.payments.models import PaymentGateway

from .base import BasePaymentProvider
from .fake import FakePaymentProvider


# =============================================================================
# PROVIDER REGISTRY
# =============================================================================

# Maps GatewayType → Provider class
_PROVIDER_MAP: dict[str, type[BasePaymentProvider]] = {
    PaymentGateway.GatewayType.FAKE: FakePaymentProvider,
    # Future providers:
    # PaymentGateway.GatewayType.ZARINPAL: ZarinPalProvider,
    # PaymentGateway.GatewayType.IDPAY: IDPayProvider,
}


def get_provider(gateway: PaymentGateway) -> Optional[BasePaymentProvider]:
    """
    Get the payment provider instance for a gateway configuration.

    Args:
        gateway: PaymentGateway model instance with type and credentials.

    Returns:
        Configured provider instance, or None if type is not registered.
    """
    provider_class = _PROVIDER_MAP.get(gateway.gateway_type)
    if provider_class is None:
        return None

    return provider_class(
        merchant_id=gateway.merchant_id,
        api_key=gateway.api_key,
    )


def register_provider(gateway_type: str, provider_class: type[BasePaymentProvider]) -> None:
    """
    Register a new payment provider.

    Args:
        gateway_type: The GatewayType string (e.g., "zarinpal").
        provider_class: The provider class implementing BasePaymentProvider.
    """
    _PROVIDER_MAP[gateway_type] = provider_class
