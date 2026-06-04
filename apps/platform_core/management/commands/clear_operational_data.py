"""
Clear operational/test data for a specific company.

Usage:
    python manage.py clear_operational_data --company-code n54 --yes

Deletes ONLY operational data for the specified company:
- OrderStatusLog
- OrderItemValue
- InvoiceItem
- PaymentAttempt
- Payment
- Invoice
- SMSOutbox
- NotificationEvent
- Notification
- Order
- Customer

Does NOT delete:
- Company, CompanyUser, OperatorPermission, Technician, TechnicianSkill,
  TechnicianCategorySkill, service categories, subcategories,
  OrderItemDefinition, SMSTemplate, SMSProvider, NotificationSetting,
  CompanySMSWallet, CompanySettings, CompanyPage, platform settings.

Safety:
- Requires --company-code
- Requires --yes to confirm
- Runs in transaction.atomic
- Prints counts before and after
"""
from django.apps import apps
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


class Command(BaseCommand):
    help = "Clear operational data for a specific company (orders, invoices, customers, SMS outbox, etc.)"

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-code",
            required=True,
            help="Company code to clear data for (e.g., n54)",
        )
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Required confirmation flag. Without this, the command will not run.",
        )

    def handle(self, *args, **options):
        company_code = options["company_code"]
        confirmed = options["yes"]

        if not confirmed:
            raise CommandError(
                "This command deletes operational data. Use --yes to confirm.\n"
                f"Example: python manage.py clear_operational_data --company-code {company_code} --yes"
            )

        from apps.tenants.models import Company

        company = Company.objects.filter(code=company_code).first()
        if company is None:
            raise CommandError(f"Company with code '{company_code}' not found.")

        self.stdout.write(f"\nClearing operational data for: {company.name} ({company.code})")
        self.stdout.write("=" * 60)

        # Define deletion order (respects FK constraints — delete children first)
        deletion_targets = [
            ("orders", "OrderStatusLog"),
            ("orders", "OrderItemValue"),
            ("invoices", "InvoiceItem"),
            ("payments", "PaymentAttempt"),
            ("payments", "Payment"),
            ("invoices", "Invoice"),
            ("sms", "SMSOutbox"),
            ("notifications", "NotificationEvent"),
            ("notifications", "Notification"),
            ("orders", "Order"),
            ("accounts", "Customer"),
        ]

        # Count before
        self.stdout.write("\nCounts BEFORE deletion:")
        counts_before = {}
        for app_label, model_name in deletion_targets:
            model = self._get_model(app_label, model_name)
            if model is None:
                continue
            qs = self._company_qs(model, company)
            count = qs.count()
            counts_before[f"{app_label}.{model_name}"] = count
            self.stdout.write(f"  {app_label}.{model_name}: {count}")

        total_before = sum(counts_before.values())
        self.stdout.write(f"\n  TOTAL: {total_before} rows")

        if total_before == 0:
            self.stdout.write(self.style.SUCCESS("\nNo operational data to clear."))
            return

        # Delete in transaction
        with transaction.atomic():
            deleted_total = 0
            for app_label, model_name in deletion_targets:
                model = self._get_model(app_label, model_name)
                if model is None:
                    continue
                qs = self._company_qs(model, company)
                count, _ = qs.delete()
                deleted_total += count
                if count > 0:
                    self.stdout.write(f"  Deleted {count} from {app_label}.{model_name}")

        # Count after
        self.stdout.write("\nCounts AFTER deletion:")
        for app_label, model_name in deletion_targets:
            model = self._get_model(app_label, model_name)
            if model is None:
                continue
            qs = self._company_qs(model, company)
            self.stdout.write(f"  {app_label}.{model_name}: {qs.count()}")

        self.stdout.write(self.style.SUCCESS(f"\nDone. Deleted {deleted_total} rows for company '{company_code}'."))

    def _get_model(self, app_label: str, model_name: str):
        try:
            return apps.get_model(app_label, model_name)
        except LookupError:
            self.stdout.write(self.style.WARNING(f"  Model {app_label}.{model_name} not found — skipping."))
            return None

    def _company_qs(self, model, company):
        """Get queryset filtered by company. Handles both company FK and nested relations."""
        # Direct company FK
        if hasattr(model, "company"):
            try:
                model._meta.get_field("company")
                return model.objects.filter(company=company)
            except Exception:
                pass

        # OrderItemValue doesn't have company directly — filter via order__company
        if model.__name__ == "OrderItemValue":
            return model.objects.filter(order__company=company)

        # PaymentAttempt — filter via payment__company
        if model.__name__ == "PaymentAttempt":
            return model.objects.filter(payment__company=company)

        # InvoiceItem — filter via invoice__company
        if model.__name__ == "InvoiceItem":
            return model.objects.filter(invoice__company=company)

        # Fallback: try company filter
        try:
            return model.objects.filter(company=company)
        except Exception:
            return model.objects.none()
