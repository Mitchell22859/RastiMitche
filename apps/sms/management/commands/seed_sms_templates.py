"""
Management command: seed_sms_templates

Creates default company SMS templates for all active companies.
The default texts come from apps.sms.default_template_texts.
Existing company-specific template text is never overwritten.
"""
from django.core.management.base import BaseCommand

from apps.notifications.models import NotificationSetting
from apps.notifications.services import NotificationSettingService
from apps.sms.default_template_texts import get_default_templates
from apps.sms.models import SMSTemplate
from apps.tenants.models import Company


DEFAULT_TEMPLATES = get_default_templates()


class Command(BaseCommand):
    help = "Seed default SMS templates for all active companies."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-code",
            type=str,
            default="",
            help="Seed only for a specific company code.",
        )

    def handle(self, *args, **options):
        company_code = options["company_code"]
        if company_code:
            companies = Company.objects.filter(code=company_code, is_active=True)
        else:
            companies = Company.objects.filter(is_active=True)

        valid_keys = {str(value) for value, _label in SMSTemplate.TemplateKey.choices}
        created_count = 0
        repaired_count = 0

        for company in companies:
            NotificationSettingService.ensure_defaults(company=company)
            settings_by_key = {
                row.event_key: row
                for row in NotificationSetting.objects.filter(company=company)
            }

            for tpl_data in DEFAULT_TEMPLATES:
                key = str(tpl_data["event_key"])
                if key not in valid_keys:
                    continue

                setting = settings_by_key.get(key)
                is_active = True if setting is None else bool(setting.sms_enabled)

                template, created = SMSTemplate.objects.get_or_create(
                    company=company,
                    key=key,
                    defaults={
                        "title": tpl_data["title"],
                        "template_text": tpl_data["template_text"],
                        "is_active": is_active,
                    },
                )
                if created:
                    created_count += 1
                    continue

                changed = False
                update_fields = []
                if not template.title:
                    template.title = tpl_data["title"]
                    update_fields.append("title")
                    changed = True
                # Repair only missing/empty text. Do not overwrite a customized text.
                if not (template.template_text or "").strip():
                    template.template_text = tpl_data["template_text"]
                    update_fields.append("template_text")
                    changed = True
                if changed:
                    update_fields.append("updated_at")
                    template.save(update_fields=update_fields)
                    repaired_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"Done. Created {created_count} templates, repaired {repaired_count} templates across {companies.count()} companies."
            )
        )
