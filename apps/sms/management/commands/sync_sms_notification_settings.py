from django.core.management.base import BaseCommand

from apps.notifications.sync import sync_company_sms_notification_state
from apps.tenants.models import Company


class Command(BaseCommand):
    help = "Sync SMSTemplate.is_active with NotificationSetting.sms_enabled."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", default="", help="Sync only one company code.")
        parser.add_argument(
            "--source",
            choices=["notification", "template"],
            default="notification",
            help=(
                "notification: NotificationSetting.sms_enabled updates SMSTemplate.is_active. "
                "template: SMSTemplate.is_active updates NotificationSetting.sms_enabled."
            ),
        )

    def handle(self, *args, **options):
        company_code = options["company_code"]
        source = options["source"]

        companies = Company.objects.filter(is_active=True)
        if company_code:
            companies = companies.filter(code=company_code)

        changed = 0
        for company in companies:
            changed += sync_company_sms_notification_state(company=company, source=source)

        self.stdout.write(self.style.SUCCESS(
            f"SMS/notification settings sync complete. Companies={companies.count()}, changed={changed}"
        ))