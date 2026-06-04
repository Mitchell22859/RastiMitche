"""
SMS - Provider Registry.

Maps provider types to implementations.
"""
from typing import Optional

from apps.sms.models import SMSProvider

from .base import BaseSMSProvider
from .fake import FakeSMSProvider


_SMS_PROVIDER_MAP: dict[str, type[BaseSMSProvider]] = {
    SMSProvider.ProviderType.FAKE: FakeSMSProvider,
    # Future:
    # SMSProvider.ProviderType.KAVENEGAR: KavenegarProvider,
}


def get_sms_provider(provider: SMSProvider) -> Optional[BaseSMSProvider]:
    """Get the SMS provider instance for a configuration."""
    provider_class = _SMS_PROVIDER_MAP.get(provider.provider_type)
    if provider_class is None:
        return None
    return provider_class(
        api_key=provider.api_key,
        sender_number=provider.sender_number,
    )
