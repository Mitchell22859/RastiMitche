"""
Payments - Operations Selectors (P13).

Read-only queries for payment operations dashboards.
No mutations. No ledger/fee creation. No invoice status changes.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db.models import Count, Sum, Q
from django.utils import timezone

from .models import Payment, PaymentGateway

PAYMENT_EXPIRATION_MINUTES = getattr(settings, "PAYMENT_EXPIRATION_MINUTES", 30)


class PaymentOperationsSelector:
    """Read-only payment health queries for operations dashboards."""

    @staticmethod
    def get_company_payment_health(company, *, limit: int = 50) -> dict:
        """
        Payment health summary for a single company.
        Used by company admin dashboard.
        """
        now = timezone.now()
        cutoff = now - timedelta(minutes=PAYMENT_EXPIRATION_MINUTES)

        # Only gateway payments (exclude cash/manual without gateway)
        gw_qs = Payment.objects.filter(company=company, gateway__isnull=False)

        # Status counts
        status_counts = dict(
            gw_qs.values_list("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )

        # Old pending (gateway, PENDING/INITIATED, older than cutoff)
        old_pending_qs = gw_qs.filter(
            status__in=[Payment.Status.PENDING, Payment.Status.INITIATED],
            created_at__lt=cutoff,
        )
        old_pending_count = old_pending_qs.count()
        old_pending_amount = int(old_pending_qs.aggregate(t=Sum("amount"))["t"] or 0)

        # Failed gateway payments (last 7 days)
        week_ago = now - timedelta(days=7)
        failed_recent = gw_qs.filter(status=Payment.Status.FAILED, created_at__gte=week_ago)
        failed_count = failed_recent.count()
        failed_amount = int(failed_recent.aggregate(t=Sum("amount"))["t"] or 0)

        # Expired by cleanup (metadata flag)
        expired_by_cleanup = gw_qs.filter(
            status=Payment.Status.FAILED,
            metadata__expired_by_cleanup=True,
        ).count()

        # Recent problematic payments (PENDING/INITIATED + FAILED, last 30 days)
        month_ago = now - timedelta(days=30)
        problematic = (
            gw_qs.filter(
                Q(status__in=[Payment.Status.PENDING, Payment.Status.INITIATED])
                | Q(status=Payment.Status.FAILED, created_at__gte=week_ago)
            )
            .select_related("invoice", "gateway")
            .order_by("-created_at")[:limit]
        )

        return {
            "status_counts": {
                "initiated": status_counts.get(Payment.Status.INITIATED, 0),
                "pending": status_counts.get(Payment.Status.PENDING, 0),
                "paid": status_counts.get(Payment.Status.PAID, 0),
                "failed": status_counts.get(Payment.Status.FAILED, 0),
                "cancelled": status_counts.get(Payment.Status.CANCELLED, 0),
            },
            "old_pending_count": old_pending_count,
            "old_pending_amount": old_pending_amount,
            "failed_recent_count": failed_count,
            "failed_recent_amount": failed_amount,
            "expired_by_cleanup_count": expired_by_cleanup,
            "problematic_payments": problematic,
            "expiration_minutes": PAYMENT_EXPIRATION_MINUTES,
        }

    @staticmethod
    def get_platform_payment_health(*, limit: int = 100) -> dict:
        """
        Global payment health for platform owner.
        Aggregates across all companies.
        """
        now = timezone.now()
        cutoff = now - timedelta(minutes=PAYMENT_EXPIRATION_MINUTES)
        week_ago = now - timedelta(days=7)

        gw_qs = Payment.objects.filter(gateway__isnull=False)

        # Global status counts
        status_counts = dict(
            gw_qs.values_list("status")
            .annotate(c=Count("id"))
            .values_list("status", "c")
        )

        # Old pending globally
        old_pending_qs = gw_qs.filter(
            status__in=[Payment.Status.PENDING, Payment.Status.INITIATED],
            created_at__lt=cutoff,
        )
        old_pending_count = old_pending_qs.count()
        old_pending_amount = int(old_pending_qs.aggregate(t=Sum("amount"))["t"] or 0)

        # Failed recently
        failed_recent = gw_qs.filter(status=Payment.Status.FAILED, created_at__gte=week_ago)
        failed_count = failed_recent.count()

        # Expired by cleanup
        expired_by_cleanup = gw_qs.filter(
            status=Payment.Status.FAILED,
            metadata__expired_by_cleanup=True,
        ).count()

        # Company breakdown (top companies by pending amount)
        company_breakdown = (
            gw_qs.filter(status__in=[Payment.Status.PENDING, Payment.Status.INITIATED])
            .values("company__code", "company__name")
            .annotate(
                pending_count=Count("id"),
                pending_amount=Sum("amount"),
            )
            .order_by("-pending_amount")[:20]
        )

        # Recent problematic payments
        problematic = (
            gw_qs.filter(
                Q(status__in=[Payment.Status.PENDING, Payment.Status.INITIATED])
                | Q(status=Payment.Status.FAILED, created_at__gte=week_ago)
            )
            .select_related("company", "invoice", "gateway")
            .order_by("-created_at")[:limit]
        )

        return {
            "status_counts": {
                "initiated": status_counts.get(Payment.Status.INITIATED, 0),
                "pending": status_counts.get(Payment.Status.PENDING, 0),
                "paid": status_counts.get(Payment.Status.PAID, 0),
                "failed": status_counts.get(Payment.Status.FAILED, 0),
                "cancelled": status_counts.get(Payment.Status.CANCELLED, 0),
            },
            "old_pending_count": old_pending_count,
            "old_pending_amount": old_pending_amount,
            "failed_recent_count": failed_count,
            "expired_by_cleanup_count": expired_by_cleanup,
            "company_breakdown": list(company_breakdown),
            "problematic_payments": problematic,
            "expiration_minutes": PAYMENT_EXPIRATION_MINUTES,
        }
