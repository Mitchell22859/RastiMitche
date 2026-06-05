#!/usr/bin/env python
"""
Minimal seed script for local development.

Creates the bare minimum records required to start working:
  - One platform owner (superuser)
  - One company with code 'n54'
  - One company admin for n54
  - One technician user for n54 (with Technician profile)

Idempotent: safe to run multiple times — uses get_or_create throughout.
Never deletes data. Never creates demo orders, invoices, or SMS outbox records.

Usage (from project root):
    python seed/minimal_seed_n54.py
"""
import os
import sys
import pathlib

# Ensure project root is on the path so Django can be found.
ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")

import django  # noqa: E402
django.setup()

from django.db import transaction  # noqa: E402

# ---------------------------------------------------------------------------
# Credentials (change before using in any non-local environment)
# ---------------------------------------------------------------------------
PLATFORM_OWNER_USERNAME = "platform_owner"
PLATFORM_OWNER_PASSWORD = "Admin@1234"

COMPANY_ADMIN_USERNAME = "n54_admin"
COMPANY_ADMIN_PASSWORD = "Admin@1234"

TECHNICIAN_USERNAME = "n54_tech"
TECHNICIAN_PASSWORD = "Admin@1234"

COMPANY_CODE = "n54"
COMPANY_NAME = "شرکت نمونه N54"


def run():
    from apps.accounts.models import CompanyUser, UserRole, Technician
    from apps.tenants.models import Company

    with transaction.atomic():
        # ------------------------------------------------------------------ #
        # 1. Company
        # ------------------------------------------------------------------ #
        company, created = Company.objects.get_or_create(
            code=COMPANY_CODE,
            defaults={
                "name": COMPANY_NAME,
                "is_active": True,
                "phone": "09100000054",
                "email": f"{COMPANY_CODE}@example.local",
                "address": "تهران",
            },
        )
        if created:
            print(f"  [+] Company created: {company.name} ({company.code})")
        else:
            print(f"  [ ] Company already exists: {company.name} ({company.code})")

        # ------------------------------------------------------------------ #
        # 2. Platform owner (superuser, no company)
        # ------------------------------------------------------------------ #
        owner, created = CompanyUser.objects.get_or_create(
            username=PLATFORM_OWNER_USERNAME,
            defaults={
                "company": None,
                "role": UserRole.PLATFORM_OWNER,
                "is_staff": True,
                "is_superuser": True,
                "first_name": "مدیر",
                "last_name": "پلتفرم",
                "email": "owner@example.local",
                "phone": "09100000001",
                "is_active": True,
            },
        )
        if created:
            owner.set_password(PLATFORM_OWNER_PASSWORD)
            owner.save(update_fields=["password"])
            print(f"  [+] Platform owner created: {owner.username}")
        else:
            print(f"  [ ] Platform owner already exists: {owner.username}")

        # ------------------------------------------------------------------ #
        # 3. Company admin
        # ------------------------------------------------------------------ #
        admin, created = CompanyUser.objects.get_or_create(
            username=COMPANY_ADMIN_USERNAME,
            defaults={
                "company": company,
                "role": UserRole.COMPANY_ADMIN,
                "is_staff": False,
                "is_superuser": False,
                "first_name": "مدیر",
                "last_name": "شرکت",
                "email": "admin@example.local",
                "phone": "09100000002",
                "is_active": True,
            },
        )
        if created:
            admin.set_password(COMPANY_ADMIN_PASSWORD)
            admin.save(update_fields=["password"])
            print(f"  [+] Company admin created: {admin.username}")
        else:
            print(f"  [ ] Company admin already exists: {admin.username}")

        # ------------------------------------------------------------------ #
        # 4. Technician user + Technician profile
        # ------------------------------------------------------------------ #
        tech_user, created = CompanyUser.objects.get_or_create(
            username=TECHNICIAN_USERNAME,
            defaults={
                "company": company,
                "role": UserRole.TECHNICIAN,
                "is_staff": False,
                "is_superuser": False,
                "first_name": "تکنسین",
                "last_name": "نمونه",
                "email": "tech@example.local",
                "phone": "09100000003",
                "is_active": True,
            },
        )
        if created:
            tech_user.set_password(TECHNICIAN_PASSWORD)
            tech_user.save(update_fields=["password"])
            print(f"  [+] Technician user created: {tech_user.username}")
        else:
            print(f"  [ ] Technician user already exists: {tech_user.username}")

        # Technician profile (OneToOne to CompanyUser)
        tech_profile, created = Technician.objects.get_or_create(
            user=tech_user,
            defaults={
                "company": company,
                "is_available": True,
            },
        )
        if created:
            print(f"  [+] Technician profile created for: {tech_user.username}")
        else:
            print(f"  [ ] Technician profile already exists for: {tech_user.username}")

    # ---------------------------------------------------------------------- #
    # Summary
    # ---------------------------------------------------------------------- #
    print()
    print("=" * 56)
    print("  MINIMAL SEED COMPLETE")
    print("=" * 56)
    print(f"  Company   : {COMPANY_CODE}  ({COMPANY_NAME})")
    print()
    print("  Username            Role              Password")
    print("  ------------------  ----------------  ----------------")
    print(f"  {PLATFORM_OWNER_USERNAME:<20}{UserRole.PLATFORM_OWNER:<18}{PLATFORM_OWNER_PASSWORD}")
    print(f"  {COMPANY_ADMIN_USERNAME:<20}{UserRole.COMPANY_ADMIN:<18}{COMPANY_ADMIN_PASSWORD}")
    print(f"  {TECHNICIAN_USERNAME:<20}{UserRole.TECHNICIAN:<18}{TECHNICIAN_PASSWORD}")
    print()
    print("  WARNING: Change all passwords before using in production.")
    print("=" * 56)


if __name__ == "__main__":
    run()
