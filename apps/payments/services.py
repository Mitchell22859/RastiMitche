"""
Payments - Service Layer.

Handles payment lifecycle: start → redirect → callback → verify.

Payment Flow:
1. Customer opens invoice → clicks "Pay"
2. PaymentStartService creates Payment + PaymentAttempt
3. Provider generates redirect URL
4. Customer is redirected to gateway
5. Gateway calls back after payment
6. PaymentVerifyService verifies with provider
7. On success: Payment → PAID, Invoice → PAID
8. On failure: Payment → FAILED, invoice stays ISSUED

IMPORTANT: Customer invoice payments use the COMPANY'S gateway.
Platform billing uses a SEPARATE system (apps/billing/).
"""
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.invoices.models import Invoice
from apps.invoices.services import InvoiceMarkPaidService

from .models import Payment, PaymentAttempt, PaymentGateway
from .providers import get_provider
from .providers.base import PaymentRequest, VerificationRequest
from .selectors import PaymentGatewaySelector


def _resolve_discount_code_id(invoice: Invoice) -> int | None:
    """Return the used DiscountCode id for this invoice, if any."""
    if not invoice or not getattr(invoice, "id", None):
        return None
    try:
        from apps.reports.models import DiscountCode
        code = (
            DiscountCode.objects
            .filter(company=invoice.company, used_invoice_id=invoice.id)
            .order_by("-used_at", "-id")
            .first()
        )
        return code.id if code else None
    except Exception:
        return None


class PaymentStartService:
    """
    Service for initiating a payment.

    Rules:
    - Invoice must be ISSUED (payable)
    - Company must have an active payment gateway
    - Creates Payment + PaymentAttempt records
    - Uses the company's configured gateway (NOT platform gateway)
    """

    @staticmethod
    @transaction.atomic
    def start(
        *,
        invoice: Invoice,
        callback_url: str,
        gateway: Optional[PaymentGateway] = None,
    ) -> tuple[Payment, PaymentAttempt, str]:
        """
        Initiate a payment for an invoice.

        Args:
            invoice: The invoice to pay (must be ISSUED).
            callback_url: URL for gateway to call back after payment.
            gateway: Optional specific gateway. Uses default if not provided.

        Returns:
            Tuple of (Payment, PaymentAttempt, redirect_url).

        Raises:
            ValueError: If invoice is not payable or no gateway available.
        """
        if not invoice.is_payable:
            raise ValueError("Invoice is not payable. Must be in ISSUED status.")

        # Get the company's payment gateway
        if gateway is None:
            gateway = PaymentGatewaySelector.get_default_for_company(
                company=invoice.company
            )

        if gateway is None:
            raise ValueError("No active payment gateway configured for this company.")

        if gateway.company_id != invoice.company_id:
            raise ValueError("Payment gateway does not belong to this company.")

        # Get provider implementation
        provider = get_provider(gateway)
        if provider is None:
            raise ValueError(f"No provider implementation for gateway type: {gateway.gateway_type}")

        # Create Payment record
        payment = Payment.objects.create(
            company=invoice.company,
            invoice=invoice,
            gateway=gateway,
            amount=invoice.total_amount,
            status=Payment.Status.INITIATED,
        )

        # Initiate with provider
        payment_request = PaymentRequest(
            amount=int(invoice.total_amount),
            invoice_number=invoice.invoice_number,
            description=f"Payment for invoice {invoice.invoice_number}",
            callback_url=callback_url,
            metadata={"payment_id": payment.id, "invoice_id": invoice.id},
        )

        response = provider.initiate_payment(payment_request)

        # Create attempt record
        attempt = PaymentAttempt.objects.create(
            company=invoice.company,
            payment=payment,
            status=(
                PaymentAttempt.AttemptStatus.REDIRECTED
                if response.success
                else PaymentAttempt.AttemptStatus.FAILED
            ),
            gateway_reference=response.reference_id,
            redirect_url=response.redirect_url if response.success else "",
            gateway_response=response.raw_response,
            error_message=response.error_message,
        )

        if response.success:
            payment.reference_id = response.reference_id
            payment.status = Payment.Status.PENDING
            payment.save(update_fields=["reference_id", "status", "updated_at"])
        else:
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status", "updated_at"])

        redirect_url = response.redirect_url if response.success else ""
        return payment, attempt, redirect_url


class PaymentVerifyService:
    """
    Service for verifying a payment after gateway callback.

    Called when the gateway redirects back to our callback URL.
    """

    @staticmethod
    @transaction.atomic
    def verify(*, payment: Payment) -> tuple[bool, str]:
        """
        Verify payment with the gateway provider.

        Args:
            payment: The payment to verify (must be PENDING).

        Returns:
            Tuple of (success: bool, message: str).
        """
        if payment.status != Payment.Status.PENDING:
            return False, "Payment is not in pending status."

        if not payment.gateway:
            return False, "Payment has no associated gateway."

        # Get provider
        provider = get_provider(payment.gateway)
        if provider is None:
            return False, "No provider implementation for this gateway."

        # Verify with provider
        verification_request = VerificationRequest(
            reference_id=payment.reference_id,
            amount=int(payment.amount),
        )

        response = provider.verify_payment(verification_request)

        # Record attempt
        PaymentAttempt.objects.create(
            company=payment.company,
            payment=payment,
            status=(
                PaymentAttempt.AttemptStatus.VERIFIED
                if response.success
                else PaymentAttempt.AttemptStatus.FAILED
            ),
            gateway_reference=payment.reference_id,
            gateway_response=response.raw_response,
            error_message=response.error_message,
        )

        if response.success:
            # Mark payment as paid
            payment.status = Payment.Status.PAID
            payment.tracking_code = response.tracking_code
            payment.paid_at = timezone.now()
            payment.save(update_fields=[
                "status", "tracking_code", "paid_at", "updated_at"
            ])

            # Mark invoice as paid and freeze settlement
            if payment.invoice and payment.invoice.status == Invoice.Status.ISSUED:
                InvoiceMarkPaidService.mark_paid(
                    invoice=payment.invoice,
                    payment=payment,
                    discount_code_id=_resolve_discount_code_id(payment.invoice),
                )

            # Record split decision snapshot (non-blocking; never raises)
            if payment.invoice:
                try:
                    from apps.payouts.services_split import PaymentSplitDecisionService
                    # Reload invoice to pick up settled_* fields written by mark_paid
                    fresh_invoice = payment.invoice.__class__.objects.get(pk=payment.invoice.pk)
                    PaymentSplitDecisionService.create_snapshot(payment, fresh_invoice)
                except Exception:
                    import logging
                    logging.getLogger(__name__).exception(
                        "Failed to create split snapshot for payment %s",
                        payment.id,
                    )

            return True, "Payment verified successfully."
        else:
            # Mark payment as failed
            payment.status = Payment.Status.FAILED
            payment.save(update_fields=["status", "updated_at"])
            return False, response.error_message or "Payment verification failed."


class PaymentCallbackService:
    """
    Service for handling gateway callbacks.

    This is the entry point when a gateway sends a callback
    (either redirect-back or server-to-server notification).
    """

    @staticmethod
    def handle_callback(
        *,
        company,
        reference_id: str,
    ) -> tuple[bool, str, Optional[Payment]]:
        """
        Handle a payment callback from the gateway.

        Args:
            company: The tenant company.
            reference_id: The gateway reference ID from the callback.

        Returns:
            Tuple of (success, message, payment).
        """
        # Find the payment by reference_id within the company
        payment = Payment.objects.filter(
            company=company,
            reference_id=reference_id,
            status=Payment.Status.PENDING,
        ).first()

        if payment is None:
            return False, "Payment not found or already processed.", None

        # Verify with provider
        success, message = PaymentVerifyService.verify(payment=payment)
        return success, message, payment
