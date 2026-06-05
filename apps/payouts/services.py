"""
Payouts - Service Layer.

All ledger mutations go through TechnicianLedgerService.
Never write TechnicianLedgerEntry directly from views or other services.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

logger = logging.getLogger(__name__)

_ONLINE_GATEWAY_TYPES = {"zarinpal", "idpay", "nextpay", "fake"}


class TechnicianLedgerService:
    """
    Financial ledger for technician wages and settlements.

    Balance convention:
      Positive balance_after → company owes technician
      Negative balance_after → technician owes company
    """

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    @staticmethod
    def get_balance(company, technician) -> int:
        """Return current technician balance in rial (positive = company owes tech)."""
        from .models import TechnicianLedgerEntry

        qs = TechnicianLedgerEntry.objects.filter(
            company=company, technician=technician
        )
        credits = (
            qs.filter(entry_type=TechnicianLedgerEntry.EntryType.CREDIT)
            .aggregate(t=Sum("amount_rial"))["t"]
            or 0
        )
        debits = (
            qs.filter(entry_type=TechnicianLedgerEntry.EntryType.DEBIT)
            .aggregate(t=Sum("amount_rial"))["t"]
            or 0
        )
        return int(credits) - int(debits)

    @staticmethod
    def list_statement(company, technician, *, limit: int = 200, offset: int = 0):
        """Return ordered ledger entries for a technician statement."""
        from .models import TechnicianLedgerEntry

        return (
            TechnicianLedgerEntry.objects.filter(
                company=company, technician=technician
            )
            .select_related("invoice", "payment", "order", "created_by")
            .order_by("-created_at", "-id")[offset : offset + limit]
        )

    # ------------------------------------------------------------------
    # Write (idempotent)
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def create_credit(
        *,
        company,
        technician,
        source: str,
        amount_rial: int,
        idempotency_key: str,
        invoice=None,
        payment=None,
        order=None,
        description: str = "",
        created_by=None,
        metadata: dict | None = None,
    ):
        """
        Create a CREDIT entry (company owes technician).
        Returns the created entry, or None if idempotency_key already exists.
        """
        return TechnicianLedgerService._write_entry(
            company=company,
            technician=technician,
            entry_type="credit",
            source=source,
            amount_rial=amount_rial,
            idempotency_key=idempotency_key,
            invoice=invoice,
            payment=payment,
            order=order,
            description=description,
            created_by=created_by,
            metadata=metadata or {},
        )

    @staticmethod
    @transaction.atomic
    def create_debit(
        *,
        company,
        technician,
        source: str,
        amount_rial: int,
        idempotency_key: str,
        invoice=None,
        payment=None,
        order=None,
        description: str = "",
        created_by=None,
        metadata: dict | None = None,
    ):
        """
        Create a DEBIT entry (technician owes company, or payout was made).
        Returns the created entry, or None if idempotency_key already exists.
        """
        return TechnicianLedgerService._write_entry(
            company=company,
            technician=technician,
            entry_type="debit",
            source=source,
            amount_rial=amount_rial,
            idempotency_key=idempotency_key,
            invoice=invoice,
            payment=payment,
            order=order,
            description=description,
            created_by=created_by,
            metadata=metadata or {},
        )

    @staticmethod
    def create_invoice_entries(invoice, payment=None) -> list:
        """
        Create all ledger entries for a newly paid invoice.

        This is the main entry point called by InvoiceMarkPaidService after
        settlement. It is fully idempotent — calling it twice for the same
        invoice produces no duplicate rows.

        Returns a list of TechnicianLedgerEntry objects that were created
        (empty if already existed or no technician wage).
        """
        from .models import TechnicianLedgerEntry

        technician = _get_technician_for_invoice(invoice)
        if technician is None:
            return []

        wage = int(invoice.settled_technician_wage or 0)
        if wage <= 0:
            return []

        payment_method = (invoice.settled_payment_method or "").lower().strip()
        created_entries = []

        # Determine whether this was an online gateway or cash payment
        is_online = payment_method in _ONLINE_GATEWAY_TYPES

        # ----------------------------------------------------------------
        # CREDIT: technician wage earned from this invoice
        # ----------------------------------------------------------------
        credit_key = f"invoice:{invoice.id}:technician_credit"
        credit_source = (
            TechnicianLedgerEntry.Source.ONLINE_GATEWAY
            if is_online
            else TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER
        )
        if not is_online:
            # Disambiguate: was it the technician or the office that collected cash?
            if _payment_collected_by_technician(payment):
                credit_source = TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER
            else:
                credit_source = TechnicianLedgerEntry.Source.MANUAL_PAYMENT

        entry = TechnicianLedgerService.create_credit(
            company=invoice.company,
            technician=technician,
            source=credit_source,
            amount_rial=wage,
            idempotency_key=credit_key,
            invoice=invoice,
            payment=payment,
            order=getattr(invoice, "order", None),
            description=f"اجرت فاکتور {invoice.invoice_number}",
        )
        if entry is not None:
            created_entries.append(entry)

        # ----------------------------------------------------------------
        # DEBIT: if technician physically collected cash from customer,
        # they hold the full invoice amount and owe the company its share.
        #
        # We only record this when the payment metadata explicitly shows the
        # technician_id, meaning the technician registered a cash receipt via
        # the technician panel. An admin marking cash (no payment object) is
        # ambiguous and NOT debited automatically.
        # ----------------------------------------------------------------
        if _payment_collected_by_technician(payment):
            total_amount = int(invoice.total_amount or 0)
            if total_amount > 0:
                debit_key = f"invoice:{invoice.id}:cash_received_by_technician"
                debit_entry = TechnicianLedgerService.create_debit(
                    company=invoice.company,
                    technician=technician,
                    source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER,
                    amount_rial=total_amount,
                    idempotency_key=debit_key,
                    invoice=invoice,
                    payment=payment,
                    order=getattr(invoice, "order", None),
                    description=(
                        f"وجه نقد دریافتی از مشتری برای فاکتور {invoice.invoice_number} "
                        f"(تکنسین نزد خود نگه داشته است)"
                    ),
                )
                if debit_entry is not None:
                    created_entries.append(debit_entry)

        return created_entries

    @staticmethod
    @transaction.atomic
    def record_manual_settlement(
        *,
        company,
        technician,
        amount_rial: int,
        direction: str,
        reference: str = "",
        description: str = "",
        created_by=None,
    ):
        """
        Record a manual settlement between company and technician.

        direction choices:
          "COMPANY_PAID_TECHNICIAN"  → DEBIT (company paid tech, balance decreases)
          "TECHNICIAN_PAID_COMPANY"  → CREDIT (tech returned money to company... wait)

        NOTE: If the technician holds cash and returns company share to the company,
        that is actually a DEBIT (reduces the debit the tech already has).
        This direction is ambiguous in the current model.

        TODO (P2): Replace `direction` with explicit entry_type once the business
        decides on canonical cash-flow terminology. For now, callers should pass
        "COMPANY_PAID_TECHNICIAN" when company wires money to technician, and
        "TECHNICIAN_PAID_COMPANY" when technician remits cash to company.
        """
        from .models import TechnicianLedgerEntry
        import uuid

        if amount_rial <= 0:
            raise ValueError("amount_rial must be positive.")

        if direction == "COMPANY_PAID_TECHNICIAN":
            entry_type = TechnicianLedgerEntry.EntryType.DEBIT
            desc = description or f"پرداخت تسویه به تکنسین — مرجع: {reference}"
        elif direction == "TECHNICIAN_PAID_COMPANY":
            # Technician returned company's share; reduce company's receivable
            # By convention: a credit here decreases technician's obligation.
            # See TODO above.
            entry_type = TechnicianLedgerEntry.EntryType.DEBIT
            desc = description or f"تحویل وجه نقد توسط تکنسین — مرجع: {reference}"
        else:
            raise ValueError(f"Unknown direction: {direction!r}")

        idempotency_key = f"manual_settlement:{uuid.uuid4().hex}"

        return TechnicianLedgerService._write_entry(
            company=company,
            technician=technician,
            entry_type=entry_type,
            source=TechnicianLedgerEntry.Source.MANUAL_SETTLEMENT,
            amount_rial=amount_rial,
            idempotency_key=idempotency_key,
            description=desc,
            created_by=created_by,
            metadata={"reference": reference, "direction": direction},
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    @transaction.atomic
    def _write_entry(
        *,
        company,
        technician,
        entry_type: str,
        source: str,
        amount_rial: int,
        idempotency_key: str,
        invoice=None,
        payment=None,
        order=None,
        description: str = "",
        created_by=None,
        metadata: dict,
    ):
        from .models import TechnicianLedgerEntry

        if TechnicianLedgerEntry.objects.filter(
            idempotency_key=idempotency_key
        ).exists():
            logger.debug(
                "TechnicianLedgerEntry idempotency hit: key=%s", idempotency_key
            )
            return None

        # Lock this technician's rows to prevent balance_after races
        TechnicianLedgerEntry.objects.select_for_update().filter(
            company=company, technician=technician
        ).order_by("-id")[:1].values_list("id", flat=True)

        current_balance = TechnicianLedgerService.get_balance(company, technician)
        if entry_type == TechnicianLedgerEntry.EntryType.CREDIT:
            balance_after = current_balance + int(amount_rial)
        else:
            balance_after = current_balance - int(amount_rial)

        return TechnicianLedgerEntry.objects.create(
            company=company,
            technician=technician,
            invoice=invoice,
            payment=payment,
            order=order,
            entry_type=entry_type,
            source=source,
            amount_rial=int(amount_rial),
            balance_after=balance_after,
            description=description,
            idempotency_key=idempotency_key,
            created_by=created_by,
            metadata=metadata,
        )


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _get_technician_for_invoice(invoice):
    """Return the Technician instance linked to the invoice via its order, or None."""
    order = getattr(invoice, "order", None)
    if order is None:
        return None
    return getattr(order, "technician", None)


def _payment_collected_by_technician(payment) -> bool:
    """
    Return True only when the payment metadata explicitly indicates that
    the technician collected the cash (set by the technician panel view).
    """
    if payment is None:
        return False
    metadata = getattr(payment, "metadata", {}) or {}
    return bool(metadata.get("technician_id"))
