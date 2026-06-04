"""
Payments - Models.

Tenant-scoped payment system for customer invoice payments.
Each company configures their own payment gateway.

IMPORTANT DISTINCTION:
- Tenant payments: Customer → Company (for services rendered)
- Platform billing: Company → Rasti Service (for SaaS subscription)

This app handles TENANT payments only.
Platform billing is in apps/billing/.
"""
from django.db import models

from apps.common.models import CompanyOwnedModel


class PaymentGateway(CompanyOwnedModel):
    """
    Payment gateway configuration for a company.
    Each company can have multiple gateways, one marked as default.
    """

    class GatewayType(models.TextChoices):
        ZARINPAL = "zarinpal", "ZarinPal"
        IDPAY = "idpay", "IDPay"
        NEXTPAY = "nextpay", "NextPay"
        FAKE = "fake", "Fake (Testing)"
        MANUAL = "manual", "Manual"

    name = models.CharField(max_length=100)
    gateway_type = models.CharField(max_length=20, choices=GatewayType.choices)
    merchant_id = models.CharField(max_length=200, blank=True)
    api_key = models.CharField(max_length=200, blank=True)
    is_active = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    callback_url = models.URLField(
        blank=True,
        help_text="Callback URL for payment verification.",
    )

    class Meta:
        unique_together = ["company", "gateway_type"]

    def __str__(self) -> str:
        return f"{self.name} ({self.gateway_type})"


class Payment(CompanyOwnedModel):
    """
    Payment transaction record.
    Links an invoice to a payment gateway attempt.

    Statuses:
        INITIATED → PENDING → PAID
        INITIATED → PENDING → FAILED
        INITIATED → CANCELLED
    """

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    invoice = models.ForeignKey(
        "invoices.Invoice",
        on_delete=models.SET_NULL,
        null=True,
        related_name="payments",
    )
    gateway = models.ForeignKey(
        PaymentGateway,
        on_delete=models.SET_NULL,
        null=True,
        related_name="payments",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.INITIATED,
        db_index=True,
    )
    reference_id = models.CharField(
        max_length=100,
        blank=True,
        help_text="Gateway-assigned reference/authority.",
    )
    tracking_code = models.CharField(
        max_length=100,
        blank=True,
        help_text="Final tracking code after successful payment.",
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["company", "status"]),
            models.Index(fields=["company", "invoice"]),
        ]

    def __str__(self) -> str:
        return f"Payment #{self.pk} - {self.status} ({self.amount})"


class PaymentAttempt(CompanyOwnedModel):
    """
    Individual attempt within a payment.
    A single Payment can have multiple attempts (retries).

    Records each interaction with the payment gateway.
    """

    class AttemptStatus(models.TextChoices):
        STARTED = "started", "Started"
        REDIRECTED = "redirected", "Redirected to Gateway"
        CALLBACK_RECEIVED = "callback_received", "Callback Received"
        VERIFIED = "verified", "Verified"
        FAILED = "failed", "Failed"

    payment = models.ForeignKey(
        Payment,
        on_delete=models.CASCADE,
        related_name="attempts",
    )
    status = models.CharField(
        max_length=20,
        choices=AttemptStatus.choices,
        default=AttemptStatus.STARTED,
    )
    gateway_reference = models.CharField(
        max_length=200,
        blank=True,
        help_text="Reference ID from gateway for this attempt.",
    )
    redirect_url = models.URLField(
        blank=True,
        help_text="URL to redirect customer to gateway.",
    )
    gateway_response = models.JSONField(
        default=dict,
        blank=True,
        help_text="Raw response from gateway.",
    )
    error_message = models.TextField(blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"Attempt #{self.pk} for Payment #{self.payment_id} - {self.status}"
