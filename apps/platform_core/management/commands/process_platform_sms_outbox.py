"""Process platform-owner SMS outbox records."""
from django.core.management.base import BaseCommand

from apps.platform_core.services_platform_sms import PlatformSMSOutboxProcessorService


class Command(BaseCommand):
    help = "Process platform-owner SMS outbox records. Does not debit any company SMS wallet."

    def add_arguments(self, parser):
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN MODE — no platform SMS will be sent.\n"))
        results = PlatformSMSOutboxProcessorService.process(limit=options["limit"], dry_run=options["dry_run"])
        self.stdout.write(self.style.SUCCESS(
            "Platform SMS Outbox Processing Complete:\n"
            f"  Scanned:  {results['scanned']}\n"
            f"  Sent:     {results['sent']}\n"
            f"  Failed:   {results['failed']}\n"
            f"  Skipped:  {results['skipped']}\n"
            f"  Dry Run:  {results['dry_run']}"
        ))
