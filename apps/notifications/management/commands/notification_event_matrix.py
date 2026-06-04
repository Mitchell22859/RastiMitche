from django.core.management.base import BaseCommand

from apps.notifications.models import NotificationSetting
from apps.notifications.services import NotificationSettingService
from apps.sms.models import SMSTemplate
from apps.tenants.models import Company


class Command(BaseCommand):
    help = "Print notification event settings and linked SMS template status for a company."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", default="n54")
        parser.add_argument("--repair", action="store_true", help="Create defaults and sync templates from notification settings.")

    def handle(self, *args, **options):
        company_code = options["company_code"]
        repair = options["repair"]

        company = Company.objects.filter(code=company_code).first()
        if not company:
            self.stderr.write(self.style.ERROR(f"Company not found: {company_code}"))
            raise SystemExit(1)

        NotificationSettingService.ensure_defaults(company=company)

        if repair:
            try:
                from apps.notifications.sync import sync_company_sms_notification_state
                changed = sync_company_sms_notification_state(company=company, source="notification")
                self.stdout.write(self.style.WARNING(f"Repaired template sync. Changed={changed}"))
            except Exception as exc:
                self.stdout.write(self.style.WARNING(f"Repair skipped: {exc}"))

        templates_by_key = {
            template.key: template
            for template in SMSTemplate.objects.filter(company=company)
        }

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"Notification Event Matrix: {company.code} - {company.name}"))
        self.stdout.write("-" * 110)
        self.stdout.write(f"{'EVENT KEY':42} | {'IN-APP':7} | {'SMS':7} | {'TEMPLATE':9} | TITLE")
        self.stdout.write("-" * 110)

        mismatch_count = 0
        missing_count = 0

        for setting in NotificationSetting.objects.filter(company=company).order_by("event_key"):
            template = templates_by_key.get(setting.event_key)
            if template is None:
                template_state = "missing"
                missing_count += 1
            else:
                template_state = "active" if template.is_active else "inactive"
                if template.is_active != setting.sms_enabled:
                    mismatch_count += 1
                    template_state += " !"

            title = setting.title or setting.get_event_key_display()
            self.stdout.write(
                f"{setting.event_key:42} | "
                f"{str(setting.in_app_enabled):7} | "
                f"{str(setting.sms_enabled):7} | "
                f"{template_state:9} | "
                f"{title}"
            )

        self.stdout.write("-" * 110)
        self.stdout.write(f"Missing templates: {missing_count}")
        self.stdout.write(f"SMS/template mismatches: {mismatch_count}")

        if mismatch_count:
            self.stderr.write(self.style.ERROR("Mismatch found. Run with --repair."))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Notification event matrix is consistent."))