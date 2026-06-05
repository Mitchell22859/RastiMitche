"""
Management command: backfill_financial_ledgers

Backfills missing TechnicianLedgerEntry and CompanyPlatformFeeEntry rows
for paid invoices that were settled before P6 was deployed.

Options:
  --dry-run           Print what would be created without writing to DB.
  --company-code CODE Limit to a single company.
  --invoice-id ID     Limit to a single invoice.
  --fix-platform-fees Only fix platform fee entries (skip technician ledger).
"""
from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Backfill missing financial ledger entries for paid invoices."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Simulate without writing.")
        parser.add_argument("--company-code", type=str, default=None, help="Limit to company code.")
        parser.add_argument("--invoice-id", type=int, default=None, help="Limit to single invoice ID.")
        parser.add_argument("--fix-platform-fees", action="store_true", help="Only fix platform fee entries.")

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        company_code = options["company_code"]
        invoice_id = options["invoice_id"]
        fees_only = options["fix_platform_fees"]

        from apps.invoices.models import Invoice
        from apps.tenants.models import Company

        qs = Invoice.objects.filter(status=Invoice.Status.PAID).select_related("company", "order__technician")

        if company_code:
            try:
                company = Company.objects.get(code=company_code)
            except Company.DoesNotExist:
                raise CommandError(f"Company '{company_code}' not found.")
            qs = qs.filter(company=company)

        if invoice_id:
            qs = qs.filter(id=invoice_id)

        total = qs.count()
        self.stdout.write(f"Found {total} paid invoice(s) to inspect.")

        tech_created = 0
        fee_created = 0

        for invoice in qs.iterator():
            if not fees_only:
                tech_created += self._backfill_tech_ledger(invoice, dry_run)
            fee_created += self._backfill_platform_fee(invoice, dry_run)

        mode = "(DRY RUN) " if dry_run else ""
        self.stdout.write(self.style.SUCCESS(
            f"{mode}Done. Tech ledger entries created: {tech_created}. "
            f"Platform fee entries created: {fee_created}."
        ))

    def _backfill_tech_ledger(self, invoice, dry_run: bool) -> int:
        from apps.payouts.services import TechnicianLedgerService
        from apps.payouts.models import TechnicianLedgerEntry

        key = f"invoice:{invoice.id}:technician_credit"
        if TechnicianLedgerEntry.objects.filter(idempotency_key=key).exists():
            return 0

        self.stdout.write(f"  [TECH] Invoice {invoice.invoice_number} (id={invoice.id}) missing tech ledger.")
        if dry_run:
            return 1
        try:
            with transaction.atomic():
                TechnicianLedgerService.create_invoice_entries(invoice, payment=None)
            return 1
        except Exception as exc:
            self.stderr.write(f"  ERROR invoice {invoice.id}: {exc}")
            return 0

    def _backfill_platform_fee(self, invoice, dry_run: bool) -> int:
        from apps.payouts.services_platform_fee import PlatformFeeService
        from apps.payouts.models import CompanyPlatformFeeEntry

        key = f"platform_fee:invoice:{invoice.id}"
        if CompanyPlatformFeeEntry.objects.filter(idempotency_key=key).exists():
            return 0

        fee_amount = PlatformFeeService.compute_fee_for_invoice(invoice)
        if fee_amount <= 0:
            return 0

        self.stdout.write(f"  [FEE] Invoice {invoice.invoice_number} (id={invoice.id}) fee={fee_amount:,} rial.")
        if dry_run:
            return 1
        try:
            with transaction.atomic():
                PlatformFeeService.record_invoice_fee(invoice)
            return 1
        except Exception as exc:
            self.stderr.write(f"  ERROR invoice {invoice.id}: {exc}")
            return 0
