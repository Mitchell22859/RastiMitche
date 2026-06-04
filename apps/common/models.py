"""
Common - Base Abstract Models.

All tenant-owned models MUST inherit from CompanyOwnedModel.
This ensures every record is linked to a company and queryable by company_id.

RULE: Never query a CompanyOwnedModel without filtering by company.
"""
from django.db import models


class TimeStampedModel(models.Model):
    """Abstract model with created_at and updated_at timestamps."""

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class CompanyOwnedModel(TimeStampedModel):
    """
    Abstract base for ALL tenant-scoped models.

    Every model that belongs to a specific company (tenant) MUST inherit this.
    This guarantees:
    - company_id is always present
    - created_at / updated_at timestamps
    - db_index on company FK for query performance

    Usage:
        class Order(CompanyOwnedModel):
            ...

    Query pattern:
        GOOD: Order.objects.filter(company=request.company)
        BAD:  Order.objects.all()  # NEVER do this for tenant models
    """

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="%(app_label)s_%(class)ss",
        db_index=True,
    )

    class Meta:
        abstract = True
