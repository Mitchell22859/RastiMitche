"""
Billing - Models.

PLATFORM-LEVEL billing for SaaS subscription payments.
Companies pay Rasti Service for platform access.

IMPORTANT DISTINCTION:
======================
- apps/payments/ = Tenant payments (Customer → Company)
- apps/billing/  = Platform billing (Company → Rasti Service)

These are completely separate systems:
- Billing uses the PLATFORM's central gateway
- Payments use each COMPANY's own gateway
- Billing is NOT tenant-scoped (no CompanyOwnedModel)
- Payments ARE tenant-scoped (CompanyOwnedModel)
"""
from django.db import models


class BillingRecord(models.Model):
    """
    Record of a company's payment to the platform (SaaS subscription).

    Platform-level model — NOT tenant-scoped.
    Managed only by PLATFORM_OWNER.
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PAID = "paid", "Paid"
        OVERDUE = "overdue", "Overdue"
        CANCELLED = "cancelled", "Cancelled"

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="billing_records",
    )
    amount = models.DecimalField(max_digits=12, decimal_places=0)
    description = models.CharField(max_length=300)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    is_paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
    due_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.company.name} - {self.amount} ({self.status})"
