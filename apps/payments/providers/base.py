"""
Payments - Base Payment Provider.

Abstract interface that all payment gateway providers must implement.
This enables swapping gateways without changing business logic.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional


@dataclass
class PaymentRequest:
    """Data needed to initiate a payment with a gateway."""
    amount: int
    invoice_number: str
    description: str
    callback_url: str
    metadata: dict


@dataclass
class PaymentResponse:
    """Response from gateway after payment initiation."""
    success: bool
    reference_id: str
    redirect_url: str
    error_message: str = ""
    raw_response: dict = None

    def __post_init__(self):
        if self.raw_response is None:
            self.raw_response = {}


@dataclass
class VerificationRequest:
    """Data needed to verify a payment callback."""
    reference_id: str
    amount: int


@dataclass
class VerificationResponse:
    """
    Response from gateway after verification.

    verified_amount: The amount the gateway actually charged (in rial).
        Real providers MUST populate this from their API response.
        Used to detect amount tampering (callback forging a different amount).
        If None, the verify service will skip amount-match check (legacy/fake mode).
    """
    success: bool
    tracking_code: str
    error_message: str = ""
    verified_amount: Optional[int] = None
    raw_response: dict = None

    def __post_init__(self):
        if self.raw_response is None:
            self.raw_response = {}


class BasePaymentProvider(ABC):
    """
    Abstract base class for payment gateway providers.

    All gateway implementations must:
    1. Implement initiate_payment() — start a payment, get redirect URL
    2. Implement verify_payment() — verify callback from gateway
    3. Implement validate_callback_signature() — verify authenticity of callback

    This abstraction allows:
    - Easy addition of new gateways
    - Testing with FakePaymentProvider
    - Swapping gateways without changing business logic

    SECURITY CONTRACT for real providers:
    - verify_payment MUST set verified_amount in the response.
    - validate_callback_signature MUST verify HMAC/signature from the PSP.
    - Returning success=True without signature check is a critical vulnerability.
    """

    def __init__(self, *, merchant_id: str = "", api_key: str = "", **kwargs):
        self.merchant_id = merchant_id
        self.api_key = api_key

    @abstractmethod
    def initiate_payment(self, request: PaymentRequest) -> PaymentResponse:
        """
        Start a payment with the gateway.

        Args:
            request: PaymentRequest with amount, description, callback_url.

        Returns:
            PaymentResponse with reference_id and redirect_url.
        """
        ...

    @abstractmethod
    def verify_payment(self, request: VerificationRequest) -> VerificationResponse:
        """
        Verify a payment after gateway callback.

        Args:
            request: VerificationRequest with reference_id and amount.

        Returns:
            VerificationResponse with success status, tracking_code, and verified_amount.

        IMPORTANT: Real providers MUST:
        - Call the PSP verify/settle API
        - Set verified_amount from the PSP's response
        - Only return success=True if signature/token is valid
        """
        ...

    def validate_callback_signature(self, callback_data: dict) -> bool:
        """
        Validate the authenticity of a gateway callback.

        Real providers MUST override this to verify HMAC, token, or signature
        from the PSP before proceeding with verification.

        Args:
            callback_data: Raw GET/POST parameters from the callback request.

        Returns:
            True if signature is valid, False otherwise.

        Default: Returns True (permissive for FAKE/testing).
        Real providers MUST override with strict validation.
        """
        return True
