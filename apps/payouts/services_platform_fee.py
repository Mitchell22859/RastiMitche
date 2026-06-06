"""
Payouts — Platform Fee Ledger Service (Payment P6).

Records and queries the per-company platform fee ledger.

Convention:
  DEBIT  → company owes platform (fee accrued on cash/manual invoice payment).
  CREDIT → company settled / platform fee paid.

Balance convention:
  Positive balance_after → company still owes platform.
  Zero / negative → company has settled (credit given).
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction

logger = logging.getLogger(__name__)


def _get_policy_fee_percent(company) -> Decimal:
    """Return platform_fee_percent for a company, or 0 if no policy."""
    try:
        from apps.tenants.models import CompanyFinancialPolicy
        policy = CompanyFinancialPolicy.objects.filter(company=company).first()
        if policy and policy.platform_fee_percent:
            return Decimal(str(policy.platform_fee_percent))
    except Exception:
        pass
    return Decimal("0")


class PlatformFeeService:
    """All platform fee ledger operations for a company."""

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get_balance(company) -> int:
        """
        Return company's outstanding platform fee balance (positive = owes platform).
        """
        from .models import CompanyPlatformFeeEntry
        from django.db.models import Sum

        qs = CompanyPlatformFeeEntry.objects.filter(company=company)
        debits = (
            qs.filter(entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT)
            .aggregate(t=Sum("amount_rial"))["t"] or 0
        )
        credits = (
            qs.filter(entry_type=CompanyPlatformFeeEntry.EntryType.CREDIT)
            .aggregate(t=Sum("amount_rial"))["t"] or 0
        )
        return int(debits) - int(credits)

    @staticmethod
    def list_entries(company, *, limit: int = 200):
        """Return ordered platform fee entries for a company."""
        from .models import CompanyPlatformFeeEntry
        return (
            CompanyPlatformFeeEntry.objects.filter(company=company)
            .select_related("invoice", "payment", "created_by")
            .order_by("-created_at", "-id")[:limit]
        )

    @staticmethod
    def compute_fee_for_invoice(invoice) -> int:
        """
        Compute platform fee amount (rial, integer, floored) for an invoice.
        Returns 0 if fee percent is 0 or no policy.
        """
        fee_pct = _get_policy_fee_percent(invoice.company)
        if not fee_pct:
            return 0
        return int(Decimal(str(invoice.total_amount)) * fee_pct / 100)

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def _write_entry(
        *,
        company,
        entry_type: str,
        source: str,
        amount_rial: int,
        idempotency_key: str,
        invoice=None,
        payment=None,
        platform_fee_percent_snapshot: Decimal = Decimal("0"),
        description: str = "",
        created_by=None,
        metadata: dict | None = None,
    ):
        """Low-level atomic write. Returns entry or None if already exists."""
        from .models import CompanyPlatformFeeEntry

        if CompanyPlatformFeeEntry.objects.filter(idempotency_key=idempotency_key).exists():
            return None

        # Compute running balance under lock — force queryset evaluation
        list(
            CompanyPlatformFeeEntry.objects.select_for_update()
            .filter(company=company)
            .order_by("-id")[:1]
            .values_list("id", flat=True)
        )

        current_balance = PlatformFeeService.get_balance(company)
        if entry_type == CompanyPlatformFeeEntry.EntryType.DEBIT:
            balance_after = current_balance + amount_rial
        else:
            balance_after = current_balance - amount_rial

        entry = CompanyPlatformFeeEntry.objects.create(
            company=company,
            entry_type=entry_type,
            source=source,
            amount_rial=amount_rial,
            balance_after=balance_after,
            platform_fee_percent_snapshot=platform_fee_percent_snapshot,
            idempotency_key=idempotency_key,
            invoice=invoice,
            payment=payment,
            description=description,
            created_by=created_by,
            metadata=metadata or {},
        )
        return entry

    @staticmethod
    def record_invoice_fee(
        invoice,
        payment=None,
        source: str | None = None,
        created_by=None,
    ):
        """
        Record a DEBIT platform fee entry for a paid invoice.

        Idempotent — calling twice for the same invoice produces no duplicate.
        Returns the created entry, or None if fee=0 or already recorded.
        """
        from .models import CompanyPlatformFeeEntry

        fee_pct = _get_policy_fee_percent(invoice.company)
        if not fee_pct:
            return None

        amount = int(Decimal(str(invoice.total_amount)) * fee_pct / 100)
        if amount <= 0:
            return None

        idempotency_key = f"platform_fee:invoice:{invoice.id}"
        resolved_source = source or CompanyPlatformFeeEntry.Source.CASH_INVOICE

        try:
            return PlatformFeeService._write_entry(
                company=invoice.company,
                entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT,
                source=resolved_source,
                amount_rial=amount,
                idempotency_key=idempotency_key,
                invoice=invoice,
                payment=payment,
                platform_fee_percent_snapshot=fee_pct,
                description=f"کارمزد پلتفرم فاکتور {invoice.invoice_number}",
                created_by=created_by,
            )
        except Exception:
            logger.exception(
                "Failed to record platform fee for invoice %s — will need backfill.",
                getattr(invoice, "id", None),
            )
            return None

    @staticmethod
    def record_manual_credit(
        company,
        amount_rial: int,
        description: str = "",
        idempotency_key: str | None = None,
        created_by=None,
    ):
        """
        Record a CREDIT (settlement) entry — company paid its platform fee.
        idempotency_key must be supplied by caller for manual entries.
        """
        from .models import CompanyPlatformFeeEntry
        import uuid
        key = idempotency_key or f"platform_fee_settlement:{uuid.uuid4().hex}"

        return PlatformFeeService._write_entry(
            company=company,
            entry_type=CompanyPlatformFeeEntry.EntryType.CREDIT,
            source=CompanyPlatformFeeEntry.Source.PLATFORM_FEE_SETTLEMENT,
            amount_rial=amount_rial,
            idempotency_key=key,
            description=description or "تسویه کارمزد پلتفرم",
            created_by=created_by,
        )
