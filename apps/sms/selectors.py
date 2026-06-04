"""
SMS selectors.

All reads are company-scoped unless explicitly processing all companies.
"""
from typing import Optional

from django.db.models import Q, QuerySet
from django.utils import timezone

from .models import SMSOutbox, SMSProvider


class SMSOutboxSelector:
    @staticmethod
    def get_for_company(*, company) -> QuerySet[SMSOutbox]:
        return SMSOutbox.objects.filter(company=company)

    @staticmethod
    def get_due_queued(*, company=None) -> QuerySet[SMSOutbox]:
        qs = SMSOutbox.objects.filter(status=SMSOutbox.Status.QUEUED).filter(
            Q(send_at__isnull=True) | Q(send_at__lte=timezone.now())
        )
        if company is not None:
            qs = qs.filter(company=company)
        return qs.select_related("company", "provider").order_by("created_at")


class SMSProviderSelector:
    @staticmethod
    def get_active_for_company(*, company) -> Optional[SMSProvider]:
        if company is None:
            return None
        return SMSProvider.objects.filter(company=company, is_active=True).order_by("id").first()
