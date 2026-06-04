"""
Management command: ensure_sms_master_templates

Creates/updates all platform master SMS templates idempotently.

Usage:
    python manage.py ensure_sms_master_templates
"""
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create or update all platform master SMS templates (idempotent)."

    def handle(self, *args, **options):
        from apps.sms.master_template_defaults import ensure_master_templates

        result = ensure_master_templates()

        self.stdout.write(
            f"Master templates: {result['created']} created, "
            f"{result['updated']} updated, {result['total']} total definitions."
        )
        self.stdout.write(self.style.SUCCESS("Done."))
