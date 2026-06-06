"""
Payments - Expiration Cleanup Service (P11).

Marks old PENDING/INITIATED gateway payments as FAILED when they exceed
the expiration window and never received a callback.

This service:
- Does NOT touch PAID payments.
- Does NOT touch manual/cash payments (no gateway attached).
- Does NOT mark invoices as paid.
- Does NOT create ledger or platform fee entries.
- IS idempotent: running twice produces the same result.
- Supports dry-run mode for safe preview.
"""
import logging
from datetime import timedelta
from typing import Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import Payment

logger = logging.getLogger(__name__)

PAYMENT_EXPIRATION_MINUTES = getattr(settings, "PAYMENT_EXPIRATION_MINUTES", 30)


class PaymentExpirationService:
    """
    Expire old pending/initiated gateway payments that never received a callback.

    Usage:
        result = PaymentExpirationService.expire_old_pending_payments()
        result = PaymentExpirationService.expire_old_pending_payments(dry_run=True)
        result = PaymentExpirationService.expire_old_pending_payments(minutes=60)
    """

    @staticmethod
    def expire_old_pending_payments(
        *,
        minutes: Optional[int] = None,
        company_code: Optional[str] = None,
        limit: int = 1000,
        dry_run: bool = False,
    ) -> dict:
        """
        Find and expire old pending/initiated gateway payments.

        Args:
            minutes: Override expiration threshold (default: PAYMENT_EXPIRATION_MINUTES).
            company_code: Limit to a specific company by code (optional).
            limit: Maximum number of payments to process in one run.
            dry_run: If True, do not write changes to DB.

        Returns:
            Dict with counts: scanned, expired, skipped_paid, skipped_no_gateway.
        """
        threshold_minutes = minutes or PAYMENT_EXPIRATION_MINUTES
        cutoff = timezone.now() - timedelta(minutes=threshold_minutes)

        # Find payments that are PENDING or INITIATED, older than cutoff,
        # and have a gateway (i.e., not manual/cash payments).
        qs = Payment.objects.filter(
            status__in=[Payment.Status.PENDING, Payment.Status.INITIATED],
            created_at__lt=cutoff,
            gateway__isnull=False,
        )

        if company_code:
            qs = qs.filter(company__code=company_code)

        qs = qs.select_related("company", "invoice").order_by("created_at")[:limit]

        scanned = 0
        expired = 0
        skipped_paid = 0
        skipped_no_gateway = 0

        for payment in qs:
            scanned += 1

            # Safety: double-check status (could have changed between query and processing)
            if payment.status == Payment.Status.PAID:
                skipped_paid += 1
                continue

            if not payment.gateway_id:
                skipped_no_gateway += 1
                continue

            if dry_run:
                expired += 1
                logger.info(
                    "[DRY RUN] Would expire payment %s (company=%s, created=%s, status=%s)",
                    payment.id,
                    getattr(payment.company, "code", "?"),
                    payment.created_at,
                    payment.status,
                )
                continue

            # Atomic update with lock to prevent race with a late callback
            with transaction.atomic():
                locked_payment = Payment.objects.select_for_update().get(pk=payment.pk)

                # Re-check after lock: if it became PAID in the meantime, skip
                if locked_payment.status == Payment.Status.PAID:
                    skipped_paid += 1
                    continue

                if locked_payment.status not in (Payment.Status.PENDING, Payment.Status.INITIATED):
                    # Already failed/cancelled — skip
                    continue

                locked_payment.status = Payment.Status.FAILED
                locked_payment.metadata = {
                    **(locked_payment.metadata or {}),
                    "expired_by_cleanup": True,
                    "expired_at": timezone.now().isoformat(),
                    "expiration_threshold_minutes": threshold_minutes,
                }
                locked_payment.save(update_fields=["status", "metadata", "updated_at"])
                expired += 1

                logger.info(
                    "Expired payment %s (company=%s, age=%s min)",
                    locked_payment.id,
                    getattr(locked_payment.company, "code", "?"),
                    threshold_minutes,
                )

        return {
            "scanned": scanned,
            "expired": expired,
            "skipped_paid": skipped_paid,
            "skipped_no_gateway": skipped_no_gateway,
            "dry_run": dry_run,
            "threshold_minutes": threshold_minutes,
        }
