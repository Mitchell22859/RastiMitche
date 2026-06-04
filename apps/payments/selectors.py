"""
Payments - Selectors.

All read operations for payments. ALWAYS company-scoped.
"""
from typing import Optional

from django.db.models import QuerySet

from .models import Payment, PaymentAttempt, PaymentGateway


class PaymentSelector:
    """Read operations for Payment records."""

    @staticmethod
    def get_for_company(*, company) -> QuerySet[Payment]:
        """Get all payments for a company."""
        return Payment.objects.filter(company=company)

    @staticmethod
    def get_for_invoice(*, company, invoice_id: int) -> QuerySet[Payment]:
        """Get payments for a specific invoice."""
        return Payment.objects.filter(company=company, invoice_id=invoice_id)

    @staticmethod
    def get_by_id_for_company(*, payment_id: int, company) -> Optional[Payment]:
        """Get a single payment by ID, company-scoped."""
        return Payment.objects.filter(id=payment_id, company=company).first()

    @staticmethod
    def get_by_reference(*, company, reference_id: str) -> Optional[Payment]:
        """Get payment by gateway reference ID."""
        return Payment.objects.filter(
            company=company, reference_id=reference_id
        ).first()

    @staticmethod
    def get_successful_for_company(*, company) -> QuerySet[Payment]:
        """Get all successful payments."""
        return Payment.objects.filter(company=company, status=Payment.Status.PAID)


    @staticmethod
    def get_latest_paid_for_invoice(*, company, invoice_id: int) -> Optional[Payment]:
        """Get the latest successful payment for one invoice, company-scoped."""
        return (
            Payment.objects
            .filter(company=company, invoice_id=invoice_id, status=Payment.Status.PAID)
            .select_related("gateway")
            .prefetch_related("attempts")
            .order_by("-paid_at", "-created_at")
            .first()
        )

    @staticmethod
    def build_display_info(payment: Optional[Payment]) -> dict:
        """Build safe display data for templates. Does not expose sensitive data."""
        if payment is None:
            return {
                "exists": False,
                "method": "",
                "method_label": "-",
                "reference": "-",
                "paid_at": None,
                "received_by": "",
                "is_cash": False,
                "is_online": False,
                "is_manual": False,
            }

        metadata = payment.metadata or {}
        method = (metadata.get("method") or "").strip().lower()
        gateway_type = getattr(getattr(payment, "gateway", None), "gateway_type", "") or ""

        if method == "cash":
            method_label = "دریافت نقدی توسط تکنسین"
        elif method == "manual" or gateway_type == "manual":
            method_label = "پرداخت دستی"
            method = method or "manual"
        else:
            method_label = "پرداخت اینترنتی"
            method = method or "online"

        gateway_reference = ""
        try:
            latest_attempt = payment.attempts.all()[0]
            gateway_reference = getattr(latest_attempt, "gateway_reference", "") or ""
        except Exception:
            gateway_reference = ""

        reference = (
            payment.tracking_code
            or payment.reference_id
            or gateway_reference
            or "-"
        )

        received_by = (
            metadata.get("received_by_username")
            or metadata.get("received_by_name")
            or metadata.get("received_by")
            or ""
        )

        return {
            "exists": True,
            "method": method,
            "method_label": method_label,
            "reference": reference,
            "paid_at": payment.paid_at,
            "received_by": received_by,
            "is_cash": method == "cash",
            "is_online": method == "online",
            "is_manual": method == "manual",
        }


class PaymentGatewaySelector:
    """Read operations for PaymentGateway."""

    @staticmethod
    def get_active_for_company(*, company) -> QuerySet[PaymentGateway]:
        """Get active gateways for a company."""
        return PaymentGateway.objects.filter(company=company, is_active=True)

    @staticmethod
    def get_default_for_company(*, company) -> Optional[PaymentGateway]:
        """Get the default active gateway for a company."""
        return PaymentGateway.objects.filter(
            company=company, is_active=True, is_default=True
        ).first()

    @staticmethod
    def get_by_type(*, company, gateway_type: str) -> Optional[PaymentGateway]:
        """Get gateway by type for a company."""
        return PaymentGateway.objects.filter(
            company=company, gateway_type=gateway_type
        ).first()
