"""
Common - Base Selector Pattern.

All selectors should follow this pattern:
- Selectors handle read operations ONLY
- Selectors return QuerySets or model instances
- Selectors never perform writes
- Selectors are the ONLY place where queries should be constructed

Usage:
    class OrderSelector(BaseCompanySelector):
        model = Order
"""
from typing import Any, Optional

from django.db import models
from django.db.models import QuerySet


class BaseSelector:
    """Base selector for non-tenant models."""

    model: Optional[type[models.Model]] = None

    @classmethod
    def get_by_id(cls, *, pk: int) -> Optional[models.Model]:
        assert cls.model is not None
        return cls.model.objects.filter(pk=pk).first()

    @classmethod
    def get_all(cls) -> QuerySet:
        assert cls.model is not None
        return cls.model.objects.all()


class BaseCompanySelector:
    """
    Base selector for tenant-scoped models.

    ALL queries MUST be filtered by company.
    This ensures data isolation between tenants.

    Usage:
        class OrderSelector(BaseCompanySelector):
            model = Order

        # In a view:
        orders = OrderSelector.get_for_company(company=request.company)
    """

    model: Optional[type[models.Model]] = None

    @classmethod
    def get_for_company(cls, *, company: Any) -> QuerySet:
        """Get all records for a specific company."""
        assert cls.model is not None
        return cls.model.objects.filter(company=company)

    @classmethod
    def get_by_id_for_company(
        cls, *, pk: int, company: Any
    ) -> Optional[models.Model]:
        """Get a single record by ID, scoped to company."""
        assert cls.model is not None
        return cls.model.objects.filter(pk=pk, company=company).first()
