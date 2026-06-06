"""
Management command: expire_pending_payments

Marks old PENDING/INITIATED gateway payments as FAILED when they exceed
the configured expiration window and never received a callback.

Safe to run via cron. Does NOT touch:
- PAID payments
- Manual/cash payments
- Invoice status
- Technician ledger
- Platform fee ledger

Usage:
    python manage.py expire_pending_payments --dry-run
    python manage.py expire_pending_payments
    python manage.py expire_pending_payments --minutes 60
    python manage.py expire_pending_payments --company-code n54
    python manage.py expire_pending_payments --limit 500
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Expire old pending gateway payments that never received a callback."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show what would be expired without making changes.",
        )
        parser.add_argument(
            "--minutes",
            type=int,
            default=None,
            help="Override expiration threshold in minutes (default: PAYMENT_EXPIRATION_MINUTES setting).",
        )
        parser.add_argument(
            "--company-code",
            type=str,
            default=None,
            help="Limit to a specific company by code.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=1000,
            help="Maximum number of payments to process (default: 1000).",
        )

    def handle(self, *args, **options):
        from apps.payments.services_expiration import PaymentExpirationService

        dry_run = options["dry_run"]
        minutes = options["minutes"]
        company_code = options["company_code"]
        limit = options["limit"]

        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be made.\n"))

        result = PaymentExpirationService.expire_old_pending_payments(
            minutes=minutes,
            company_code=company_code,
            limit=limit,
            dry_run=dry_run,
        )

        self.stdout.write("")
        self.stdout.write(f"  Threshold:         {result['threshold_minutes']} minutes")
        self.stdout.write(f"  Scanned:           {result['scanned']}")
        self.stdout.write(f"  Expired:           {result['expired']}")
        self.stdout.write(f"  Skipped (paid):    {result['skipped_paid']}")
        self.stdout.write(f"  Skipped (no gw):   {result['skipped_no_gateway']}")
        self.stdout.write("")

        if dry_run:
            self.stdout.write(self.style.WARNING(
                f"DRY RUN complete. {result['expired']} payment(s) would be expired."
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"Done. {result['expired']} payment(s) expired."
            ))
