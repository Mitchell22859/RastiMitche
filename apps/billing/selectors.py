"""Billing - Selectors."""
from django.db.models import QuerySet

from .models import BillingRecord


class BillingSelector:
    @staticmethod
    def get_for_company(*, company_id: int) -> QuerySet[BillingRecord]:
        return BillingRecord.objects.filter(company_id=company_id)
