"""Check company SMS wallet credit and queue platform-paid alerts."""
from __future__ import annotations

from django.core.management.base import BaseCommand

from apps.platform_core.services_sms_credit_alerts import SMSCreditAlertService


class Command(BaseCommand):
    help = "Check company SMS credits and queue platform-paid low/empty credit alerts."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", default="", help="Limit to one company code, e.g. n54")
        parser.add_argument("--threshold-rial", type=int, default=None, help="Low-credit threshold in rial")
        parser.add_argument("--dry-run", action="store_true", default=False)
        parser.add_argument("--force", action="store_true", default=False, help="Ignore daily dedup key and create another event")

    def handle(self, *args, **options):
        results = SMSCreditAlertService.check_all(
            company_code=options["company_code"],
            threshold_rial=options["threshold_rial"],
            dry_run=options["dry_run"],
            force=options["force"],
        )

        queued = 0
        ok = 0
        skipped = 0

        for item in results:
            line = (
                f"company={item.company_code} "
                f"balance={item.balance_rial} "
                f"threshold={item.threshold_rial} "
                f"status={item.status}"
            )
            if item.event_key:
                line += f" event={item.event_key}"
            if item.event_id:
                line += f" event_id={item.event_id}"

            if item.status == "queued":
                queued += 1
                self.stdout.write(self.style.SUCCESS(line))
            elif item.status == "ok":
                ok += 1
                self.stdout.write(line)
            else:
                skipped += 1
                self.stdout.write(self.style.WARNING(line))

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("SMS credit alert check complete:"))
        self.stdout.write(f"  Companies checked: {len(results)}")
        self.stdout.write(f"  Queued events:      {queued}")
        self.stdout.write(f"  OK:                 {ok}")
        self.stdout.write(f"  Skipped/other:      {skipped}")
        self.stdout.write(f"  Dry run:            {options['dry_run']}")
