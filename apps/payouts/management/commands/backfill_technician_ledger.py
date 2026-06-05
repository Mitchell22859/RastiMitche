"""
Management command: backfill_technician_ledger

Finds all paid invoices that have a technician wage but no corresponding ledger
CREDIT entry, then creates the missing entries idempotently.

Usage:
    python manage.py backfill_technician_ledger
    python manage.py backfill_technician_ledger --dry-run
    python manage.py backfill_technician_ledger --company-id 3
"""
from django.core.management.base import BaseCommand
from django.db import transaction


class Command(BaseCommand):
    help = "Backfill TechnicianLedgerEntry rows for paid invoices that are missing ledger entries."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Print what would be created without writing to the database.",
        )
        parser.add_argument(
            "--company-id",
            type=int,
            default=None,
            help="Limit backfill to a single company by ID.",
        )

    def handle(self, *args, **options):
        from apps.invoices.models import Invoice
        from apps.payouts.models import TechnicianLedgerEntry
        from apps.payouts.services import TechnicianLedgerService, _get_technician_for_invoice

        dry_run = options["dry_run"]
        company_id = options["company_id"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no database writes."))

        # Find paid invoices with a technician wage
        qs = Invoice.objects.filter(
            status=Invoice.Status.PAID,
        ).exclude(
            settled_technician_wage__isnull=True,
        ).exclude(
            settled_technician_wage=0,
        ).select_related("order__technician", "company")

        if company_id:
            qs = qs.filter(company_id=company_id)

        total = qs.count()
        self.stdout.write(f"Found {total} paid invoices with technician wage.")

        created = 0
        skipped = 0
        no_tech = 0

        for invoice in qs.iterator():
            technician = _get_technician_for_invoice(invoice)
            if technician is None:
                no_tech += 1
                continue

            credit_key = f"invoice:{invoice.id}:technician_credit"
            already_exists = TechnicianLedgerEntry.objects.filter(
                idempotency_key=credit_key
            ).exists()

            if already_exists:
                skipped += 1
                continue

            if dry_run:
                self.stdout.write(
                    f"  [DRY] Would create CREDIT for invoice {invoice.invoice_number} "
                    f"(id={invoice.id}) tech={technician.id} "
                    f"amount={invoice.settled_technician_wage}"
                )
                created += 1
                continue

            try:
                with transaction.atomic():
                    TechnicianLedgerService.create_invoice_entries(invoice)
                created += 1
                self.stdout.write(f"  Created ledger entry for invoice {invoice.invoice_number}")
            except Exception as exc:
                self.stderr.write(
                    f"  ERROR for invoice {invoice.id}: {exc}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\nDone. Created: {created} | Skipped (already existed): {skipped} "
                f"| No technician: {no_tech}"
            )
        )
