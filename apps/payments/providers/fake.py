"""
Payments - Fake Payment Provider.

Used for testing and development.
Simulates a payment gateway without external API calls.
"""
import uuid

from .base import (
    BasePaymentProvider,
    PaymentRequest,
    PaymentResponse,
    VerificationRequest,
    VerificationResponse,
)


class FakePaymentProvider(BasePaymentProvider):
    """
    Fake payment provider for testing.

    Behavior:
    - initiate_payment: Always succeeds, returns a fake redirect URL.
    - verify_payment: Succeeds if reference_id starts with "SUCCESS",
      fails if it starts with "FAIL".

    Usage in tests:
        provider = FakePaymentProvider()
        response = provider.initiate_payment(request)
        # response.success is True
        # response.redirect_url is "https://fake-gateway.test/pay/<ref>"
    """

    def initiate_payment(self, request: PaymentRequest) -> PaymentResponse:
        """Always succeeds with a fake reference and redirect URL."""
        reference = f"SUCCESS-{uuid.uuid4().hex[:12]}"
        redirect_url = f"https://fake-gateway.test/pay/{reference}"

        return PaymentResponse(
            success=True,
            reference_id=reference,
            redirect_url=redirect_url,
            raw_response={"status": "ok", "authority": reference},
        )

    def verify_payment(self, request: VerificationRequest) -> VerificationResponse:
        """
        Succeeds if reference_id starts with 'SUCCESS'.
        Fails if reference_id starts with 'FAIL'.
        """
        if request.reference_id.startswith("SUCCESS"):
            tracking_code = f"TRACK-{uuid.uuid4().hex[:8]}"
            return VerificationResponse(
                success=True,
                tracking_code=tracking_code,
                raw_response={"status": "verified", "ref_id": tracking_code},
            )
        else:
            return VerificationResponse(
                success=False,
                tracking_code="",
                error_message="Payment was not completed.",
                raw_response={"status": "failed"},
            )
