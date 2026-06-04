"""Process queued SMS outbox records."""
from django.core.management.base import BaseCommand, CommandError

from apps.sms.services import SMSOutboxProcessorService
from apps.tenants.models import Company


class Command(BaseCommand):
    help = "Process queued SMS outbox records with strict company isolation."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", type=str, default=None)
        parser.add_argument("--limit", type=int, default=100)
        parser.add_argument("--dry-run", action="store_true", default=False)

    def handle(self, *args, **options):
        company_code = options["company_code"]
        company = None

        if company_code:
            company = Company.objects.filter(code=company_code).first()
            if company is None:
                raise CommandError(f"Company with code '{company_code}' not found.")

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN MODE — no messages will be sent.\n"))

        results = SMSOutboxProcessorService.process(
            company=company,
            limit=options["limit"],
            dry_run=options["dry_run"],
        )

        self.stdout.write(self.style.SUCCESS(
            "SMS Outbox Processing Complete:\n"
            f"  Scanned:  {results['scanned']}\n"
            f"  Sent:     {results['sent']}\n"
            f"  Failed:   {results['failed']}\n"
            f"  Skipped:  {results['skipped']}\n"
            f"  Dry Run:  {results['dry_run']}"
        ))
