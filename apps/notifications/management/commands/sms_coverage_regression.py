"""Regression checks for SMS/notification event catalog coverage."""
from django.core.management.base import BaseCommand

from apps.notifications.event_catalog import (
    EVENT_DEFINITIONS,
    get_internal_only_events,
    get_sms_supported_events,
)
from apps.notifications.models import NotificationSetting
from apps.notifications.services import NotificationSettingService
from apps.sms.default_template_texts import SMS_DEFAULT_TEMPLATES, validate_default_templates
from apps.sms.models import SMSTemplate
from apps.tenants.models import Company


class Command(BaseCommand):
    help = "Verify SMS/notification event catalog, template, and company provisioning coverage."

    def add_arguments(self, parser):
        parser.add_argument("--verbose", action="store_true")
        parser.add_argument("--company-code", default="")

    def handle(self, *args, **options):
        verbose = bool(options.get("verbose"))
        failures: list[str] = []
        passed = 0

        def ok(label: str, condition: bool, detail: str = ""):
            nonlocal passed
            if condition:
                passed += 1
                if verbose:
                    self.stdout.write(self.style.SUCCESS(f"[OK] {label}"))
            else:
                msg = f"[FAIL] {label}"
                if detail:
                    msg += f" — {detail}"
                failures.append(msg)
                self.stdout.write(self.style.ERROR(msg))

        all_events = set(EVENT_DEFINITIONS.keys())
        sms_events = {event.key for event in get_sms_supported_events()}
        internal_events = {event.key for event in get_internal_only_events()}
        sms_choices = {str(value) for value, _label in SMSTemplate.TemplateKey.choices}
        setting_choices = {str(value) for value, _label in NotificationSetting.EventKey.choices}
        default_rows = {str(row["event_key"]) for row in NotificationSettingService.default_rows()}
        default_templates = set(SMS_DEFAULT_TEMPLATES.keys())

        ok("total events == 46", len(all_events) == 46, str(len(all_events)))
        ok("sms-supported events == 39", len(sms_events) == 39, str(len(sms_events)))
        ok("internal-only events == 7", len(internal_events) == 7, str(len(internal_events)))
        ok("all SMS events have default SMS text", sms_events <= default_templates, str(sorted(sms_events - default_templates)))
        ok("no internal-only event has required SMS text", not (internal_events & default_templates), str(sorted(internal_events & default_templates)))
        ok("all SMS events are in SMSTemplate choices", sms_events <= sms_choices, str(sorted(sms_events - sms_choices)))
        ok("all events are in NotificationSetting choices", all_events <= setting_choices, str(sorted(all_events - setting_choices)))
        ok("NotificationSettingService.default_rows includes all events", all_events <= default_rows, str(sorted(all_events - default_rows)))
        ok("central template text validation has no errors", not validate_default_templates(), str(validate_default_templates()))

        qs = Company.objects.all().order_by("id")
        if options.get("company_code"):
            qs = qs.filter(code=options["company_code"])
        for company in qs:
            try:
                from apps.sms.provisioning import provision_company_communication_defaults

                provision_company_communication_defaults(company)
            except Exception:
                NotificationSettingService.ensure_defaults(company=company)
            sms_count = SMSTemplate.objects.filter(company=company).count()
            setting_count = NotificationSetting.objects.filter(company=company).count()
            ok(f"{company.code}: NotificationSetting rows >= 46", setting_count >= 46, str(setting_count))
            ok(f"{company.code}: SMSTemplate rows >= 39", sms_count >= 39, str(sms_count))

        total = passed + len(failures)
        self.stdout.write("")
        if failures:
            self.stdout.write(self.style.ERROR(f"SMS coverage regression: PASSED {passed}, FAILED {len(failures)}, TOTAL {total}"))
            raise SystemExit(1)
        self.stdout.write(self.style.SUCCESS(f"SMS coverage regression: PASSED {passed}, FAILED 0, TOTAL {total}"))
