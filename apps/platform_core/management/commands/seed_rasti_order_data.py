"""Seed the operational Rasti order data for an existing tenant."""
from django.core.management.base import BaseCommand
from django.db import transaction

from apps.accounts.models import Technician, TechnicianCategorySkill
from apps.orders.models import OrderItemDefinition
from apps.tenants.models import Company, CompanyServiceCategory


class Command(BaseCommand):
    help = "Create Rasti-style service category, dynamic order items, and technician priorities."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", default="n54")

    @transaction.atomic
    def handle(self, *args, **options):
        company_code = options["company_code"]
        company = Company.objects.filter(code=company_code).first()
        if not company:
            raise SystemExit(f"Company not found: {company_code}")

        category, _ = CompanyServiceCategory.objects.get_or_create(
            company=company,
            title="نصب پکیج و رادیاتور",
            defaults={"is_active": True, "sort_order": 0},
        )

        items = [
            ("پکیج ایران", OrderItemDefinition.Kind.NUMBER),
            ("پکیج بوتان", OrderItemDefinition.Kind.NUMBER),
            ("پکیج خارجی", OrderItemDefinition.Kind.NUMBER),
            ("رادیاتور", OrderItemDefinition.Kind.NUMBER),
            ("کوپل بندی", OrderItemDefinition.Kind.NUMBER),
        ]
        for index, (title, kind) in enumerate(items):
            OrderItemDefinition.objects.get_or_create(
                company=company,
                category=category,
                title=title,
                defaults={"kind": kind, "is_active": True, "sort_order": index},
            )

        technicians = Technician.objects.filter(company=company, is_available=True)
        for tech in technicians:
            TechnicianCategorySkill.objects.get_or_create(
                technician=tech,
                category=category,
                defaults={"priority": TechnicianCategorySkill.Priority.P1},
            )

        self.stdout.write(self.style.SUCCESS(
            f"Rasti order data is ready for {company.name}: category, items, and technician priorities."
        ))
