"""
Management command: seed demo users and company for local development.

Usage:
    python manage.py seed_demo

Creates:
    - Company: n54 (active)
    - platform_owner / password123 (PLATFORM_OWNER)
    - n54_admin / password123 (COMPANY_ADMIN, company=n54)
    - n54_tech / password123 (TECHNICIAN, company=n54)
"""
from django.core.management.base import BaseCommand

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company, CompanyPage, CompanySettings


class Command(BaseCommand):
    help = "Seed demo company and users for local development."

    def handle(self, *args, **options):
        # Create company
        company, created = Company.objects.get_or_create(
            code="n54",
            defaults={
                "name": "شرکت نمونه ۵۴",
                "slug": "n54",
                "is_active": True,
                "phone": "02112345678",
                "email": "info@n54.ir",
            },
        )
        if created:
            CompanySettings.objects.get_or_create(company=company)
            CompanyPage.objects.get_or_create(
                company=company, defaults={"title": company.name}
            )
            self.stdout.write(f"  Created company: {company.name} ({company.code})")
        else:
            self.stdout.write(f"  Company exists: {company.name} ({company.code})")

        # Demo users (CUSTOMER role removed — no customer portal)
        demo_users = [
            {
                "username": "platform_owner",
                "phone": "09100000001",
                "role": UserRole.PLATFORM_OWNER,
                "company": None,
                "first_name": "مدیر",
                "last_name": "پلتفرم",
            },
            {
                "username": "n54_admin",
                "phone": "09100000002",
                "role": UserRole.COMPANY_ADMIN,
                "company": company,
                "first_name": "مدیر",
                "last_name": "شرکت",
            },
            {
                "username": "n54_tech",
                "phone": "09100000003",
                "role": UserRole.TECHNICIAN,
                "company": company,
                "first_name": "علی",
                "last_name": "تکنسین",
            },
        ]

        for user_data in demo_users:
            username = user_data["username"]
            if CompanyUser.objects.filter(username=username).exists():
                self.stdout.write(f"  User exists: {username}")
                continue

            user = CompanyUser.objects.create_user(
                username=username,
                password="password123",
                phone=user_data["phone"],
                role=user_data["role"],
                company=user_data["company"],
                first_name=user_data["first_name"],
                last_name=user_data["last_name"],
            )
            if user_data["role"] == UserRole.PLATFORM_OWNER:
                user.is_staff = True
                user.is_superuser = True
                user.save(update_fields=["is_staff", "is_superuser"])

            self.stdout.write(f"  Created user: {username} ({user_data['role']})")

        self.stdout.write(self.style.SUCCESS("\nDone! Demo data seeded."))
        self.stdout.write("  Login at /login/ with username/password123")
