from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.test import Client, override_settings


@dataclass(frozen=True)
class UrlCheck:
    label: str
    path: str
    expected: tuple[int, ...]


class Command(BaseCommand):
    help = "Smoke-check the seeded demo URLs without relying on Django test files."

    def add_arguments(self, parser):
        parser.add_argument(
            "--company-code",
            default="n54",
            help="Seeded company code to check. Default: n54",
        )
        parser.add_argument(
            "--password",
            default="password123",
            help="Seeded password. Default: password123",
        )

    def handle(self, *args, **options):
        company_code = options["company_code"]
        password = options["password"]

        User = get_user_model()
        errors: list[str] = []

        def find_user(phone: str):
            try:
                return User.objects.get(phone=phone)
            except User.DoesNotExist:
                errors.append(
                    f"Missing user '{phone}'. Run: python manage.py seed_demo"
                )
                return None

        platform_owner = find_user("platform_owner")
        admin = find_user(f"{company_code}_admin")
        technician = find_user(f"{company_code}_tech")
        customer = find_user(f"{company_code}_customer")

        common_checks = [
            UrlCheck("platform login", "/loginlogin/", (200, 302)),
            UrlCheck("favicon", "/favicon.ico", (200, 304)),
            UrlCheck("company public home", f"/{company_code}/", (200, 302)),
            UrlCheck("company login", f"/{company_code}/login/", (200, 302)),
        ]

        platform_checks = [
            UrlCheck("platform dashboard", "/loginlogin/dashboard/", (200, 302)),
        ]

        admin_checks = [
            UrlCheck("admin dashboard", f"/{company_code}/admin/", (200,)),
            UrlCheck("admin orders", f"/{company_code}/admin/orders/", (200,)),
            UrlCheck("admin settings", f"/{company_code}/admin/settings/", (200,)),
            UrlCheck("admin sms templates", f"/{company_code}/admin/sms/templates/", (200,)),
        ]

        technician_checks = [
            UrlCheck("tech dashboard", f"/{company_code}/tech/", (200,)),
            UrlCheck("tech available orders", f"/{company_code}/tech/orders/available/", (200,)),
            UrlCheck("tech my orders", f"/{company_code}/tech/orders/my/", (200,)),
            UrlCheck("tech notifications", f"/{company_code}/tech/notifications/", (200, 302)),
            UrlCheck("old available orders redirect", f"/{company_code}/orders/available/", (301, 302)),
            UrlCheck("old my orders redirect", f"/{company_code}/orders/my/", (301, 302)),
        ]

        customer_checks = [
            UrlCheck("customer dashboard/home", f"/{company_code}/dashboard/", (200, 302, 404)),
        ]

        with override_settings(ALLOWED_HOSTS=["testserver", "127.0.0.1", "localhost", "*"]):
            self._run_checks(Client(), common_checks, errors)

            if platform_owner:
                client = Client()
                client.force_login(platform_owner)
                self._run_checks(client, platform_checks, errors)

            if admin:
                client = Client()
                client.force_login(admin)
                self._run_checks(client, admin_checks, errors)

            if technician:
                client = Client()
                client.force_login(technician)
                self._run_checks(client, technician_checks, errors)

            if customer:
                client = Client()
                client.force_login(customer)
                self._run_checks(client, customer_checks, errors)

        if errors:
            self.stdout.write("")
            self.stdout.write(self.style.ERROR("Smoke check failed:"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("Seeded URL smoke check passed."))

    def _run_checks(self, client: Client, checks: Iterable[UrlCheck], errors: list[str]) -> None:
        for check in checks:
            try:
                response = client.get(check.path, follow=False)
                status_code = response.status_code
            except Exception as exc:
                errors.append(f"{check.label}: {check.path} raised {type(exc).__name__}: {exc}")
                continue

            if status_code not in check.expected:
                errors.append(
                    f"{check.label}: {check.path} returned {status_code}, expected {check.expected}"
                )
            else:
                self.stdout.write(f"[OK] {check.label}: {check.path} -> {status_code}")
