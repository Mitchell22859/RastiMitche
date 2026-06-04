from django.core.management.base import BaseCommand

from apps.notifications.services import NotificationSettingService
from apps.tenants.models import Company


class Command(BaseCommand):
    help = "Seed default notification settings for active companies."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", default="", help="Seed only one company code.")

    def handle(self, *args, **options):
        company_code = options["company_code"]
        qs = Company.objects.filter(is_active=True)
        if company_code:
            qs = qs.filter(code=company_code)

        total = 0
        for company in qs:
            rows = NotificationSettingService.ensure_defaults(company=company)
            total += len(rows)

        self.stdout.write(self.style.SUCCESS(
            f"Notification settings ready. Companies={qs.count()}, rows={total}"
        ))
