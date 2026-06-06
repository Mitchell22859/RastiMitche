"""
Payments - Reconciliation Service (P12).

Provider-neutral reconciliation engine for comparing internal Payment records
with external PSP settlement reports.

AUDIT-ONLY by design:
- Does NOT mark invoices as PAID.
- Does NOT create ledger entries.
- Does NOT create platform fee entries.
- Does NOT modify payment status.
- Outputs mismatches for manual review.

Usage:
    from apps.payments.services_reconciliation import (
        PaymentReconciliationService, ProviderReportRow,
    )

    rows = [ProviderReportRow(provider_reference="REF-123", amount=5000000, status="paid")]
    result = PaymentReconciliationService.reconcile(provider_rows=rows, company_code="n54")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Optional

from .models import Payment

logger = logging.getLogger(__name__)


# =============================================================================
# VALUE OBJECTS
# =============================================================================

@dataclass
class ProviderReportRow:
    """One row from an external PSP settlement report."""
    provider_reference: str
    amount: int  # In rial
    status: str  # e.g. "paid", "failed", "pending", "refunded"
    paid_at: str = ""  # ISO datetime string, optional
    raw_id: str = ""  # Optional PSP-internal ID


@dataclass
class ReconciliationRecord:
    """Result of matching one provider row or internal payment."""
    provider_reference: str
    expected_amount: int = 0
    provider_amount: int = 0
    expected_status: str = ""
    provider_status: str = ""
    matched: bool = False
    issue_code: str = ""
    issue_message: str = ""
    payment_id: Optional[int] = None
    invoice_id: Optional[int] = None
    company_code: str = ""


@dataclass
class ReconciliationSummary:
    """Aggregate result of a reconciliation run."""
    scanned: int = 0
    matched: int = 0
    missing_in_provider: int = 0
    missing_in_internal: int = 0
    amount_mismatch: int = 0
    status_mismatch: int = 0
    duplicate_references: int = 0
    errors: int = 0
    records: list = field(default_factory=list)

    @property
    def has_issues(self) -> bool:
        return (
            self.missing_in_provider > 0
            or self.missing_in_internal > 0
            or self.amount_mismatch > 0
            or self.status_mismatch > 0
            or self.duplicate_references > 0
            or self.errors > 0
        )


# =============================================================================
# STATUS MAPPING
# =============================================================================

_PROVIDER_STATUS_MAP = {
    "paid": "paid",
    "successful": "paid",
    "success": "paid",
    "verified": "paid",
    "failed": "failed",
    "failure": "failed",
    "error": "failed",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "refunded": "refunded",
    "pending": "pending",
}


def _normalize_provider_status(raw: str) -> str:
    """Normalize provider status string to internal vocabulary."""
    return _PROVIDER_STATUS_MAP.get(raw.strip().lower(), raw.strip().lower())


# =============================================================================
# SERVICE
# =============================================================================

class PaymentReconciliationService:
    """
    Reconcile internal Payment records against external PSP report rows.

    This is audit-only — no database modifications are made.
    """

    @staticmethod
    def reconcile(
        *,
        provider_rows: list[ProviderReportRow],
        company_code: Optional[str] = None,
        gateway_type: Optional[str] = None,
        limit: int = 5000,
    ) -> ReconciliationSummary:
        """
        Compare provider report rows with internal payment records.

        Args:
            provider_rows: Parsed rows from PSP settlement export.
            company_code: Limit to a specific company (optional).
            gateway_type: Filter by gateway type (optional).
            limit: Max internal payments to scan for missing-in-provider check.

        Returns:
            ReconciliationSummary with all match/mismatch details.
        """
        summary = ReconciliationSummary()

        # 1. Build lookup from provider rows
        provider_map: dict[str, list[ProviderReportRow]] = {}
        for row in provider_rows:
            ref = row.provider_reference.strip()
            if not ref:
                summary.errors += 1
                summary.records.append(ReconciliationRecord(
                    provider_reference="",
                    issue_code="empty_reference",
                    issue_message="Provider row has empty reference.",
                    provider_amount=row.amount,
                    provider_status=row.status,
                ))
                continue
            provider_map.setdefault(ref, []).append(row)

        # 2. Detect duplicate references
        for ref, rows in provider_map.items():
            if len(rows) > 1:
                summary.duplicate_references += 1
                summary.records.append(ReconciliationRecord(
                    provider_reference=ref,
                    issue_code="duplicate_provider_reference",
                    issue_message=f"Provider reference appears {len(rows)} times.",
                    provider_amount=rows[0].amount,
                    provider_status=rows[0].status,
                ))

        # 3. Match provider rows against internal payments
        matched_payment_ids = set()

        for ref, rows in provider_map.items():
            row = rows[0]  # Use first occurrence
            summary.scanned += 1
            normalized_status = _normalize_provider_status(row.status)

            # Find internal payment by reference_id
            qs = Payment.objects.filter(reference_id=ref)
            if company_code:
                qs = qs.filter(company__code=company_code)
            if gateway_type:
                qs = qs.filter(gateway__gateway_type=gateway_type)

            payment = qs.first()

            if payment is None:
                summary.missing_in_internal += 1
                summary.records.append(ReconciliationRecord(
                    provider_reference=ref,
                    provider_amount=row.amount,
                    provider_status=normalized_status,
                    issue_code="missing_in_internal",
                    issue_message="Provider reports payment but no matching internal record found.",
                ))
                continue

            matched_payment_ids.add(payment.id)
            internal_status = payment.status.lower()
            internal_amount = int(payment.amount)
            record = ReconciliationRecord(
                provider_reference=ref,
                expected_amount=internal_amount,
                provider_amount=row.amount,
                expected_status=internal_status,
                provider_status=normalized_status,
                payment_id=payment.id,
                invoice_id=payment.invoice_id,
                company_code=getattr(payment.company, "code", ""),
            )

            # Check amount
            if row.amount != internal_amount:
                record.matched = False
                record.issue_code = "amount_mismatch"
                record.issue_message = (
                    f"Amount mismatch: internal={internal_amount}, provider={row.amount}"
                )
                summary.amount_mismatch += 1
                summary.records.append(record)
                continue

            # Check status
            if normalized_status == "paid" and internal_status != "paid":
                record.matched = False
                record.issue_code = "status_mismatch_provider_paid"
                record.issue_message = (
                    f"Provider says PAID but internal status is '{internal_status}'. "
                    "Needs manual review — do NOT auto-settle."
                )
                summary.status_mismatch += 1
                summary.records.append(record)
                continue

            if normalized_status == "failed" and internal_status == "pending":
                record.matched = False
                record.issue_code = "status_mismatch_provider_failed"
                record.issue_message = (
                    f"Provider says FAILED but internal is still PENDING. "
                    "Consider expiring this payment."
                )
                summary.status_mismatch += 1
                summary.records.append(record)
                continue

            # Status matches or is compatible
            record.matched = True
            summary.matched += 1

        # 4. Find internal payments missing from provider report
        #    (only gateway payments in PENDING/PAID status within scope)
        internal_qs = Payment.objects.filter(
            gateway__isnull=False,
            status__in=[Payment.Status.PENDING, Payment.Status.PAID],
        ).exclude(id__in=matched_payment_ids)

        if company_code:
            internal_qs = internal_qs.filter(company__code=company_code)
        if gateway_type:
            internal_qs = internal_qs.filter(gateway__gateway_type=gateway_type)

        for payment in internal_qs.select_related("company")[:limit]:
            if payment.reference_id and payment.reference_id.strip() not in provider_map:
                summary.missing_in_provider += 1
                summary.records.append(ReconciliationRecord(
                    provider_reference=payment.reference_id,
                    expected_amount=int(payment.amount),
                    expected_status=payment.status,
                    payment_id=payment.id,
                    invoice_id=payment.invoice_id,
                    company_code=getattr(payment.company, "code", ""),
                    issue_code="missing_in_provider",
                    issue_message=(
                        f"Internal payment {payment.id} (status={payment.status}) "
                        "not found in provider report."
                    ),
                ))

        return summary


# =============================================================================
# CSV PARSING
# =============================================================================

def parse_reconciliation_csv(file_path: str) -> tuple[list[ProviderReportRow], list[str]]:
    """
    Parse a reconciliation CSV file into ProviderReportRow objects.

    Expected columns (header row required):
        provider_reference, amount, status

    Optional columns:
        paid_at, raw_id

    Returns:
        (rows, errors) — errors is a list of human-readable issues.
    """
    import csv

    rows = []
    errors = []

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)

            if not reader.fieldnames:
                return [], ["CSV file is empty or has no header row."]

            # Validate required columns
            required = {"provider_reference", "amount", "status"}
            actual = {col.strip().lower() for col in reader.fieldnames}
            missing = required - actual
            if missing:
                return [], [f"Missing required columns: {', '.join(sorted(missing))}"]

            for i, raw_row in enumerate(reader, start=2):
                ref = (raw_row.get("provider_reference") or "").strip()
                amount_str = (raw_row.get("amount") or "").strip().replace(",", "")
                status = (raw_row.get("status") or "").strip()

                if not ref:
                    errors.append(f"Row {i}: empty provider_reference, skipped.")
                    continue

                try:
                    amount = int(amount_str)
                except (ValueError, TypeError):
                    errors.append(f"Row {i}: invalid amount '{amount_str}', skipped.")
                    continue

                if not status:
                    errors.append(f"Row {i}: empty status, skipped.")
                    continue

                rows.append(ProviderReportRow(
                    provider_reference=ref,
                    amount=amount,
                    status=status,
                    paid_at=(raw_row.get("paid_at") or "").strip(),
                    raw_id=(raw_row.get("raw_id") or "").strip(),
                ))

    except FileNotFoundError:
        return [], [f"File not found: {file_path}"]
    except Exception as e:
        return [], [f"Error reading CSV: {e}"]

    return rows, errors
