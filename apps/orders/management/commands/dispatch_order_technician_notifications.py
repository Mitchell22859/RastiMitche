"""Dispatch technician notifications for currently visible NEW orders."""
from __future__ import annotations

from django.core.management.base import BaseCommand
from apps.orders.technician_notifications import dispatch_due_order_notifications_for_company
from apps.tenants.models import Company


class Command(BaseCommand):
    help = (
        "Notify technicians about NEW unassigned orders that are currently "
        "visible according to category, priority, workload, and future-order rules."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-code",
            dest="company_code",
            default="",
            help="Optional tenant company code, e.g. n54.",
        )
        parser.add_argument(
            "--no-sms",
            action="store_true",
            help="Create in-app notifications but do not queue technician SMS.",
        )

    def handle(self, *args, **options):
        company_code = (options.get("company_code") or "").strip()
        send_sms = not options.get("no_sms")
        companies = Company.objects.filter(is_active=True)
        if company_code:
            companies = companies.filter(code=company_code)

        total_orders = 0
        total_notifications = 0
        total_sms = 0

        for company in companies:
            summary = dispatch_due_order_notifications_for_company(
                company=company,
                send_sms=send_sms,
            )
            total_orders += summary.checked_orders
            total_notifications += summary.created_notifications
            total_sms += summary.queued_sms

        self.stdout.write(self.style.SUCCESS(
            f"Checked {total_orders} order(s). "
            f"Created {total_notifications} technician notification(s). "
            f"Queued {total_sms} SMS message(s)."
        ))
