"""
Management command: reconcile_payments

Compares internal Payment records with an external PSP settlement report (CSV).

AUDIT-ONLY: Does NOT modify any data. Outputs reconciliation summary and issues.

Usage:
    python manage.py reconcile_payments --file report.csv --dry-run
    python manage.py reconcile_payments --file report.csv --company-code n54
    python manage.py reconcile_payments --file report.csv --gateway-type fake

CSV Format (required columns):
    provider_reference, amount, status

Optional columns:
    paid_at, raw_id
"""
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Reconcile internal payments against a PSP settlement report (CSV). Audit-only."

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            type=str,
            required=True,
            help="Path to the PSP reconciliation CSV file.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=True,
            help="Audit-only mode (default: always audit-only in this version).",
        )
        parser.add_argument(
            "--company-code",
            type=str,
            default=None,
            help="Limit reconciliation to a specific company.",
        )
        parser.add_argument(
            "--gateway-type",
            type=str,
            default=None,
            help="Filter by gateway type (e.g., 'fake', 'zarinpal').",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=5000,
            help="Max internal payments to scan for missing-in-provider (default: 5000).",
        )

    def handle(self, *args, **options):
        from apps.payments.services_reconciliation import (
            PaymentReconciliationService,
            parse_reconciliation_csv,
        )

        file_path = options["file"]
        company_code = options["company_code"]
        gateway_type = options["gateway_type"]
        limit = options["limit"]

        self.stdout.write(self.style.WARNING("AUDIT-ONLY MODE — no data will be modified.\n"))
        self.stdout.write(f"  File: {file_path}")
        if company_code:
            self.stdout.write(f"  Company: {company_code}")
        if gateway_type:
            self.stdout.write(f"  Gateway: {gateway_type}")
        self.stdout.write("")

        # Parse CSV
        rows, parse_errors = parse_reconciliation_csv(file_path)

        if parse_errors:
            for err in parse_errors:
                self.stderr.write(self.style.ERROR(f"  PARSE: {err}"))
            if not rows:
                raise CommandError("No valid rows parsed from CSV. Aborting.")
            self.stdout.write("")

        self.stdout.write(f"  Parsed {len(rows)} valid row(s) from CSV.\n")

        # Run reconciliation
        summary = PaymentReconciliationService.reconcile(
            provider_rows=rows,
            company_code=company_code,
            gateway_type=gateway_type,
            limit=limit,
        )

        # Print summary
        self.stdout.write("=" * 50)
        self.stdout.write("  RECONCILIATION SUMMARY")
        self.stdout.write("=" * 50)
        self.stdout.write(f"  Provider rows scanned:     {summary.scanned}")
        self.stdout.write(f"  Matched:                   {summary.matched}")
        self.stdout.write(f"  Missing in internal DB:    {summary.missing_in_internal}")
        self.stdout.write(f"  Missing in provider:       {summary.missing_in_provider}")
        self.stdout.write(f"  Amount mismatch:           {summary.amount_mismatch}")
        self.stdout.write(f"  Status mismatch:           {summary.status_mismatch}")
        self.stdout.write(f"  Duplicate references:      {summary.duplicate_references}")
        self.stdout.write(f"  Errors:                    {summary.errors}")
        self.stdout.write("=" * 50)

        # Print issues
        issues = [r for r in summary.records if not r.matched]
        if issues:
            self.stdout.write(self.style.WARNING(f"\n  {len(issues)} issue(s) found:\n"))
            for record in issues[:100]:  # Limit output
                self.stdout.write(
                    f"  [{record.issue_code}] ref={record.provider_reference} "
                    f"internal_amount={record.expected_amount} provider_amount={record.provider_amount} "
                    f"internal_status={record.expected_status} provider_status={record.provider_status} "
                    f"payment_id={record.payment_id} — {record.issue_message}"
                )
            if len(issues) > 100:
                self.stdout.write(f"\n  ... and {len(issues) - 100} more issues (truncated).")
        else:
            self.stdout.write(self.style.SUCCESS("\n  All records matched. No issues found."))

        self.stdout.write("")
        if summary.has_issues:
            self.stdout.write(self.style.WARNING(
                "  ACTION REQUIRED: Review issues above. "
                "Do NOT auto-settle — verify with PSP before any manual correction."
            ))
        else:
            self.stdout.write(self.style.SUCCESS("  Reconciliation complete. No action needed."))
