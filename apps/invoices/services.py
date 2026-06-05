"""
Invoices - Service Layer.

All write operations for invoices.
Business logic MUST live here, never in views.
"""
from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Customer

from .models import Invoice, InvoiceItem, generate_invoice_number


def _money(value, default=0) -> Decimal:
    if value in (None, ""):
        return Decimal(default)
    try:
        return Decimal(str(value).replace(",", "").strip() or default)
    except Exception:
        return Decimal(default)


def build_invoice_snapshot_from_order(order) -> dict[str, Any]:
    technician = order.technician
    technician_user = technician.user if technician else None
    return {
        "customer_name_snapshot": order.display_customer_name,
        "customer_phone_snapshot": order.display_customer_phone,
        "address_snapshot": order.address or "",
        "technician_name_snapshot": technician_user.get_full_name() if technician_user else "",
        "technician_phone_snapshot": technician_user.phone if technician_user else "",
        "service_title_snapshot": str(order.service_category or order.title or ""),
        "service_date_snapshot": order.service_date,
    }


class InvoiceDuplicateGuard:
    """
    Prevents duplicate invoices for the same order.

    An "active" invoice is any invoice for the same company and order
    where status is NOT cancelled.
    """

    @staticmethod
    def get_active_for_order(*, company, order) -> Optional[Invoice]:
        """
        Return the existing active (non-cancelled) invoice for an order,
        or None if no active invoice exists.
        """
        if order is None:
            return None
        return (
            Invoice.objects
            .filter(company=company, order=order)
            .exclude(status=Invoice.Status.CANCELLED)
            .order_by("-created_at")
            .first()
        )

    @staticmethod
    def has_active_for_order(*, company, order) -> bool:
        """Check if an active invoice already exists for the order."""
        if order is None:
            return False
        return (
            Invoice.objects
            .filter(company=company, order=order)
            .exclude(status=Invoice.Status.CANCELLED)
            .exists()
        )


class InvoiceCreateService:
    """
    Service for creating invoices.

    Rules:
    - Invoice must belong to a company
    - Customer, if present, must belong to the same company
    - Invoice number is auto-generated per company
    - Initial status is DRAFT
    """

    @staticmethod
    @transaction.atomic
    def create(
        *,
        company,
        customer: Customer | None = None,
        order=None,
        items: Optional[list[dict[str, Any]]] = None,
        notes: str = "",
        tax_amount=0,
        discount_amount=0,
        created_by=None,
        footer_text: str = "",
        **snapshots,
    ) -> Invoice:
        if customer and customer.company_id != company.id:
            raise ValueError("Customer does not belong to this company.")

        invoice = Invoice(
            company=company,
            customer=customer,
            order=order,
            created_by=created_by,
            invoice_number=generate_invoice_number(company),
            status=Invoice.Status.DRAFT,
            tax_amount=_money(tax_amount),
            extra_discount_amount=_money(discount_amount),
            notes=notes or "",
            footer_text=footer_text or Invoice._meta.get_field("footer_text").default,
            **snapshots,
        )
        invoice.save()

        InvoiceItemBulkService.replace_items(invoice=invoice, items=items or [])
        invoice.recalculate_totals(save=True)
        return invoice

    @staticmethod
    @transaction.atomic
    def create_from_order(*, order, created_by=None) -> Invoice:
        """
        Create a draft invoice from an order.
        The order is operational; prices are entered on the invoice afterwards.
        """
        snapshots = build_invoice_snapshot_from_order(order)
        invoice = InvoiceCreateService.create(
            company=order.company,
            customer=order.customer,
            order=order,
            created_by=created_by,
            items=[],
            **snapshots,
        )
        return invoice

    @staticmethod
    @transaction.atomic
    def get_or_create_for_order(*, order, created_by=None) -> tuple[Invoice, bool]:
        """
        Return existing active invoice for the order, or create a new DRAFT.

        Returns:
            (invoice, created) — created is True if a new invoice was made.
        """
        existing = InvoiceDuplicateGuard.get_active_for_order(
            company=order.company, order=order
        )
        if existing is not None:
            return existing, False

        invoice = InvoiceCreateService.create_from_order(
            order=order, created_by=created_by
        )
        return invoice, True


class InvoiceUpdateService:
    """Update draft invoice header + line items."""

    @staticmethod
    @transaction.atomic
    def update(
        *,
        invoice: Invoice,
        data: dict[str, Any],
        items: list[dict[str, Any]],
    ) -> Invoice:
        if invoice.status != Invoice.Status.DRAFT:
            raise ValueError("Only draft invoices can be edited.")

        # Snapshot/header fields are intentionally immutable after invoice creation.
        # They represent the exact order/customer/technician data at the time the
        # invoice draft was generated and must not be changed from the edit form.
        invoice.tax_amount = _money(data.get("tax_amount"))
        invoice.extra_discount_amount = _money(data.get("discount_amount"))
        invoice.save()

        InvoiceItemBulkService.replace_items(invoice=invoice, items=items)
        invoice.recalculate_totals(save=True)
        return invoice


class InvoiceItemBulkService:
    """Replace invoice rows from a simple POST-style payload."""

    @staticmethod
    @transaction.atomic
    def replace_items(*, invoice: Invoice, items: list[dict[str, Any]]) -> None:
        InvoiceItem.objects.filter(company=invoice.company, invoice=invoice).delete()
        rows = []
        for idx, item in enumerate(items):
            description = (item.get("description") or "").strip()
            if not description:
                continue
            quantity = _money(item.get("quantity"), default=1)
            if quantity <= 0:
                quantity = Decimal("1")
            unit_price = _money(item.get("unit_price"))
            discount = _money(item.get("discount_amount"))
            row_type = item.get("row_type", InvoiceItem.RowType.SERVICE)
            if row_type not in (InvoiceItem.RowType.SERVICE, InvoiceItem.RowType.GOODS, InvoiceItem.RowType.TRAVEL):
                row_type = InvoiceItem.RowType.SERVICE
            rows.append(
                InvoiceItem(
                    company=invoice.company,
                    invoice=invoice,
                    description=description,
                    row_type=row_type,
                    quantity=quantity,
                    unit_price=unit_price,
                    discount_amount=discount,
                    total_price=max(0, quantity * unit_price - discount),
                    sort_order=idx,
                )
            )
        if rows:
            InvoiceItem.objects.bulk_create(rows)


class InvoiceIssueService:
    """Service for issuing invoices (DRAFT → ISSUED)."""

    @staticmethod
    @transaction.atomic
    def issue(*, invoice: Invoice) -> Invoice:
        if invoice.status != Invoice.Status.DRAFT:
            raise ValueError("Only draft invoices can be issued.")

        invoice.recalculate_totals(save=True)
        if invoice.total_amount <= 0:
            raise ValueError("Cannot issue invoice with zero or negative amount.")

        # Snapshot technician wage percentages at issue time
        from .services_wage import snapshot_wage_percentages_on_invoice
        snapshot_wage_percentages_on_invoice(invoice)

        invoice.status = Invoice.Status.ISSUED
        invoice.issued_at = timezone.now()
        invoice.save(update_fields=["status", "issued_at", "updated_at"])
        return invoice


class InvoiceCancelService:
    """Service for cancelling invoices."""

    @staticmethod
    @transaction.atomic
    def cancel(*, invoice: Invoice, reason: str = "") -> Invoice:
        if invoice.status not in [Invoice.Status.DRAFT, Invoice.Status.ISSUED]:
            raise ValueError("Only draft or issued invoices can be cancelled.")

        invoice.status = Invoice.Status.CANCELLED
        if reason:
            invoice.notes = f"{invoice.notes}\nلغو: {reason}".strip()
        invoice.save(update_fields=["status", "notes", "updated_at"])
        return invoice


class InvoiceMarkPaidService:
    """Mark issued invoices as paid and freeze financial settlement."""

    @staticmethod
    @transaction.atomic
    def mark_paid(
        *,
        invoice: Invoice,
        payment=None,
        payment_method: str = "",
        payment_reference: str = "",
        discount_code_id: int | None = None,
    ) -> Invoice:
        if invoice.status != Invoice.Status.ISSUED:
            raise ValueError("Only issued invoices can be marked as paid.")
        if getattr(invoice, "settled_at", None) is not None:
            raise ValueError("Invoice is already settled.")

        if payment is not None:
            if getattr(payment, "company_id", None) != invoice.company_id:
                raise ValueError("Payment does not belong to invoice company.")
            if getattr(payment, "invoice_id", None) != invoice.id:
                raise ValueError("Payment does not belong to invoice.")
            if payment.amount != invoice.total_amount:
                raise ValueError("Payment amount does not match invoice total. Please restart payment.")

            gateway = getattr(payment, "gateway", None)
            payment_method = (
                getattr(gateway, "gateway_type", "")
                or (getattr(payment, "metadata", {}) or {}).get("method", "")
                or payment_method
                or "online"
            )
            payment_reference = (
                getattr(payment, "tracking_code", "")
                or getattr(payment, "reference_id", "")
                or payment_reference
                or ""
            )

        if not payment_method:
            payment_method = "cash"

        from .services_settlement import InvoiceSettlementService

        InvoiceSettlementService.settle(
            invoice=invoice,
            payment_method=payment_method,
            payment_reference=payment_reference,
            discount_code_id=discount_code_id,
        )

        invoice.status = Invoice.Status.PAID
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_at", "updated_at"])

        # Create technician ledger entries after settlement is frozen.
        # Import is deferred to avoid circular import; this call is idempotent.
        try:
            from apps.payouts.services import TechnicianLedgerService
            TechnicianLedgerService.create_invoice_entries(invoice, payment=payment)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to create ledger entries for invoice %s — ledger will need backfill.",
                getattr(invoice, "id", None),
            )

        # Record platform fee receivable for cash/manual payments (P6).
        try:
            from apps.payouts.services_platform_fee import PlatformFeeService
            PlatformFeeService.record_invoice_fee(invoice, payment=payment)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to record platform fee for invoice %s — ledger will need backfill.",
                getattr(invoice, "id", None),
            )

        return invoice
