"""Billing - Service Layer."""
from typing import Any

from .models import BillingRecord


class BillingService:
    @staticmethod
    def create_billing_record(*, data: dict[str, Any]) -> BillingRecord:
        record = BillingRecord(**data)
        record.full_clean()
        record.save()
        return record
