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
    """Response from gateway after verification."""
    success: bool
    tracking_code: str
    error_message: str = ""
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

    This abstraction allows:
    - Easy addition of new gateways
    - Testing with FakePaymentProvider
    - Swapping gateways without changing business logic
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
            VerificationResponse with success status and tracking_code.
        """
        ...
