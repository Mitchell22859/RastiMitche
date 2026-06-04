from django.core.management.base import BaseCommand

from apps.accounts.models import OperatorPermission
from apps.accounts.operator_access import (
    get_operator_queryset,
    get_user_display,
    get_user_identifier,
    list_operator_permission_items,
)
from apps.tenants.models import Company


class Command(BaseCommand):
    help = "List operators or audit an operator permissions."

    def add_arguments(self, parser):
        parser.add_argument("--company-code", default="n54")
        parser.add_argument("--operator-id", type=int, default=0)
        parser.add_argument("--contains", default="", help="Filter permission keys/path/title containing this text.")
        parser.add_argument("--list-operators", action="store_true", help="List operator IDs for this company.")

    def handle(self, *args, **options):
        company_code = options["company_code"]
        operator_id = options["operator_id"]
        contains = (options["contains"] or "").lower().strip()
        list_operators = options["list_operators"]

        company = Company.objects.filter(code=company_code).first()
        if not company:
            self.stderr.write(self.style.ERROR(f"Company not found: {company_code}"))
            raise SystemExit(1)

        operators = get_operator_queryset(company)

        if list_operators or not operator_id:
            self.stdout.write("")
            self.stdout.write(self.style.SUCCESS(f"Operators for company {company.code} - {company.name}"))
            self.stdout.write("-" * 90)
            self.stdout.write(f"{'ID':6} | {'ACTIVE':7} | {'IDENTIFIER':25} | NAME")
            self.stdout.write("-" * 90)

            count = 0
            for operator in operators:
                active = "yes" if getattr(operator, "is_active", False) else "no"
                self.stdout.write(
                    f"{operator.id:<6} | {active:<7} | {get_user_identifier(operator):25} | {get_user_display(operator)}"
                )
                count += 1

            self.stdout.write("-" * 90)
            self.stdout.write(f"Operators found: {count}")

            if not operator_id:
                self.stdout.write("")
                self.stdout.write("برای گزارش دسترسی، از ID واقعی یکی از اپراتورهای بالا استفاده کنید.")
                self.stdout.write("Example:")
                self.stdout.write(f"python manage.py operator_permission_report --company-code {company.code} --operator-id <ID> --contains invoice")
                return

        operator = operators.filter(id=operator_id).first()
        if not operator:
            self.stderr.write(self.style.ERROR(f"Operator not found with id={operator_id} in company {company.code}."))
            self.stdout.write("")
            self.stdout.write("Available operators:")
            for item in operators:
                self.stdout.write(f"  id={item.id} | {get_user_identifier(item)} | {get_user_display(item)}")
            raise SystemExit(1)

        allowed = set(
            OperatorPermission.objects.filter(
                company=company,
                operator=operator,
                is_allowed=True,
            ).values_list("permission_key", flat=True)
        )

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(
            f"Operator permission report: id={operator.id} | {get_user_display(operator)} / {get_user_identifier(operator)}"
        ))
        self.stdout.write("-" * 120)
        self.stdout.write(f"{'STATE':8} | {'KEY':40} | {'GROUP':15} | TITLE")
        self.stdout.write("-" * 120)

        found = 0
        invoice_allowed = []

        for item in list_operator_permission_items():
            haystack = f"{item.key} {item.path_template} {item.title} {item.description}".lower()
            if contains and contains not in haystack:
                continue

            state = "ALLOW" if item.key in allowed else "DENY"
            if "invoice" in haystack and state == "ALLOW":
                invoice_allowed.append(item.key)

            self.stdout.write(f"{state:8} | {item.key:40} | {item.group:15} | {item.title}")
            found += 1

        self.stdout.write("-" * 120)
        self.stdout.write(f"Shown permissions: {found}")
        self.stdout.write(f"Total allowed permissions: {len(allowed)}")

        if invoice_allowed:
            self.stdout.write(self.style.WARNING("Invoice permissions currently allowed:"))
            for key in invoice_allowed:
                self.stdout.write(f"  - {key}")
        else:
            self.stdout.write(self.style.SUCCESS("No invoice permissions are allowed for this operator."))
