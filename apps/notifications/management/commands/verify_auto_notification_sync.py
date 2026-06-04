from django.core.management.base import BaseCommand

from apps.notifications.models import NotificationSetting
from apps.notifications.services import NotificationSettingService
from apps.sms.models import SMSTemplate
from apps.tenants.models import Company


class Command(BaseCommand):
    help = "Verify automatic SMS/template sync between NotificationSetting and SMSTemplate."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", default="n54")

    def handle(self, *args, **options):
        company_code = options["company_code"]
        company = Company.objects.filter(code=company_code).first()
        if not company:
            self.stderr.write(self.style.ERROR(f"Company not found: {company_code}"))
            raise SystemExit(1)

        NotificationSettingService.ensure_defaults(company=company)

        setting = NotificationSetting.objects.filter(
            company=company,
            event_key=NotificationSetting.EventKey.ORDER_AVAILABLE_TECHNICIAN,
        ).first()

        template = SMSTemplate.objects.filter(
            company=company,
            key=NotificationSetting.EventKey.ORDER_AVAILABLE_TECHNICIAN,
        ).first()

        if not setting or not template:
            self.stdout.write(self.style.WARNING("Matching setting/template not found; skipping deep verification."))
            return

        old_setting_sms = setting.sms_enabled
        old_template_active = template.is_active

        try:
            setting.sms_enabled = False
            setting.save(update_fields=["sms_enabled", "updated_at"])
            template.refresh_from_db()
            if template.is_active is not False:
                raise AssertionError("NotificationSetting -> SMSTemplate auto sync failed.")

            template.is_active = True
            template.save(update_fields=["is_active", "updated_at"])
            setting.refresh_from_db()
            if setting.sms_enabled is not True:
                raise AssertionError("SMSTemplate -> NotificationSetting auto sync failed.")

            self.stdout.write(self.style.SUCCESS("Automatic SMS/notification sync verified."))
        finally:
            NotificationSetting.objects.filter(pk=setting.pk).update(sms_enabled=old_setting_sms)
            SMSTemplate.objects.filter(pk=template.pk).update(is_active=old_template_active)