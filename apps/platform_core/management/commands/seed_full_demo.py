"""
Demo/Test Seed Command — full multi-tenant dataset for local development.

Usage:
    python manage.py seed_full_demo
    python manage.py seed_full_demo --reset

--reset: Deletes all operational data for the 3 demo companies and the
         platform_owner user, then re-seeds. Does NOT delete migrations,
         static files, or source code.

WARNING: For local development only. Never run against production.
"""
from __future__ import annotations

import random
from datetime import date, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

User = get_user_model()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEMO_PASSWORD = "123456789"

COMPANY_DEFS = [
    {"name": "شرکت خدماتی ن۵۴", "code": "n54"},
    {"name": "شرکت خدماتی رایان", "code": "rayan"},
    {"name": "شرکت خدماتی سپید", "code": "sepid"},
]

TECHNICIAN_DATA = {
    "n54": [
        {"username": "n54_tech1", "first_name": "علی", "last_name": "محمدی", "phone": "09121000101", "wage": 30},
        {"username": "n54_tech2", "first_name": "حسین", "last_name": "رضایی", "phone": "09121000102", "wage": 40},
        {"username": "n54_tech3", "first_name": "مهدی", "last_name": "کریمی", "phone": "09121000103", "wage": 50},
    ],
    "rayan": [
        {"username": "rayan_tech1", "first_name": "رضا", "last_name": "احمدی", "phone": "09131000101", "wage": 30},
        {"username": "rayan_tech2", "first_name": "سعید", "last_name": "حسینی", "phone": "09131000102", "wage": 40},
        {"username": "rayan_tech3", "first_name": "امیر", "last_name": "نجفی", "phone": "09131000103", "wage": 50},
    ],
    "sepid": [
        {"username": "sepid_tech1", "first_name": "محمد", "last_name": "صادقی", "phone": "09141000101", "wage": 30},
        {"username": "sepid_tech2", "first_name": "جواد", "last_name": "موسوی", "phone": "09141000102", "wage": 40},
        {"username": "sepid_tech3", "first_name": "داود", "last_name": "ابراهیمی", "phone": "09141000103", "wage": 50},
    ],
}

CATEGORIES = [
    {
        "title": "نظافت منزل",
        "items": [
            {"title": "نظافت عمومی واحد", "base_price": 800000},
            {"title": "نظافت کامل واحد", "base_price": 1500000},
        ],
    },
    {
        "title": "نظافت راه‌پله و مشاعات",
        "items": [
            {"title": "نظافت هفتگی راه‌پله", "base_price": 400000},
            {"title": "نظافت کامل مشاعات", "base_price": 900000},
        ],
    },
    {
        "title": "شستشو و خدمات ویژه",
        "items": [
            {"title": "شستشوی مبل", "base_price": 600000},
            {"title": "شستشوی فرش", "base_price": 1200000},
        ],
    },
]

CUSTOMER_DATA = [
    {"first_name": "زهرا", "last_name": "رضایی", "phone_suffix": "001", "address": "تهران، ونک، خیابان ملاصدرا"},
    {"first_name": "فاطمه", "last_name": "محمدی", "phone_suffix": "002", "address": "تهران، تهرانپارس، خیابان رزمندگان"},
    {"first_name": "مریم", "last_name": "احمدی", "phone_suffix": "003", "address": "تهران، پونک، بلوار فردوس"},
    {"first_name": "سارا", "last_name": "کریمی", "phone_suffix": "004", "address": "تهران، نارمک، خیابان دماوند"},
    {"first_name": "نرگس", "last_name": "حسینی", "phone_suffix": "005", "address": "تهران، یوسف‌آباد، خیابان جهان‌آرا"},
    {"first_name": "لیلا", "last_name": "موسوی", "phone_suffix": "006", "address": "تهران، شریعتی، کوچه باغ صبا"},
    {"first_name": "آرزو", "last_name": "صادقی", "phone_suffix": "007", "address": "تهران، مرزداران، خیابان برق"},
    {"first_name": "شیرین", "last_name": "نجفی", "phone_suffix": "008", "address": "تهران، شهران، بلوار بهاران"},
    {"first_name": "منصوره", "last_name": "ابراهیمی", "phone_suffix": "009", "address": "تهران، اکباتان، فاز ۳"},
    {"first_name": "پریسا", "last_name": "قاسمی", "phone_suffix": "010", "address": "تهران، سعادت‌آباد، میدان کاج"},
]

# Order statuses that do NOT auto-create an invoice (avoid DONE)
ORDER_STATUSES = [
    "NEW", "NEW", "NEW",
    "WAITING", "WAITING",
    "IN_PROGRESS", "IN_PROGRESS", "IN_PROGRESS",
    "CANCEL_REQUESTED",
    "CANCELLED",
]

ORDER_DESCRIPTIONS = [
    "نظافت کامل آپارتمان ۸۰ متری",
    "شستشوی فرش و مبل سالن پذیرایی",
    "نظافت هفتگی راه‌پله ۵ طبقه",
    "نظافت عمومی واحد مسکونی",
    "شستشوی فرش اتاق خواب",
    "نظافت مشاعات ساختمان",
    "نظافت کامل ویلا",
    "شستشوی مبل راحتی",
    "نظافت قبل از اسباب‌کشی",
    "نظافت بعد از بازسازی",
]

# Operator order-related permission keys
OPERATOR_ORDER_PERMISSIONS = [
    "admin_orders",
    "admin_order_detail",
    "admin_order_create",
    "admin_order_edit",
    "admin_order_assign",
    "admin_customers",
    "admin_customer_detail",
    "admin_customer_lookup",
    "admin_requests",
]

# Merchant profile seed variety per company
MERCHANT_PROFILE_VARIANTS = {
    "n54": "approved",
    "rayan": "under_review",
    "sepid": "not_submitted",
}

# Financial policy seed per company
FINANCIAL_POLICY = {
    "n54":    {"payout_strategy": "SPLIT_WITH_TECHNICIAN", "platform_fee_percent": "1.00"},
    "rayan":  {"payout_strategy": "DIRECT_TO_COMPANY",     "platform_fee_percent": "1.00"},
    "sepid":  {"payout_strategy": "SPLIT_WITH_TECHNICIAN", "platform_fee_percent": "0.00"},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _phone_for_company(company_code: str, suffix: str) -> str:
    prefix = {"n54": "0912200", "rayan": "0913200", "sepid": "0914200"}.get(company_code, "0912200")
    return prefix + suffix


def _make_user(username, password, role, company=None, first_name="", last_name="", phone=""):
    from apps.accounts.models import UserRole

    user, created = User.objects.get_or_create(
        username=username,
        defaults={
            "role": role,
            "company": company,
            "first_name": first_name,
            "last_name": last_name,
            "phone": phone,
            "is_active": True,
            "must_change_password": False,
        },
    )
    if not created:
        user.role = role
        user.company = company
        user.first_name = first_name
        user.last_name = last_name
        user.phone = phone
        user.is_active = True
        user.must_change_password = False
    user.set_password(password)
    user.save()
    return user, created


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------

def _reset_demo_data(stdout):
    from apps.accounts.models import Technician, OperatorPermission
    from apps.tenants.models import (
        Company, CompanyMerchantProfile, CompanyMerchantProfileChangeRequest,
        CompanyFinancialPolicy, CompanyServiceCategory, CompanyServiceSubCategory,
        CompanySettings, CompanyPage,
    )
    from apps.orders.models import Order, OrderStatusLog

    stdout.write("\n⚠️  RESET: Deleting demo operational data...\n")

    codes = [d["code"] for d in COMPANY_DEFS]
    companies = Company.objects.filter(code__in=codes)
    company_ids = list(companies.values_list("id", flat=True))

    # Orders (cascade deletes OrderStatusLog, OrderItemValue)
    deleted_orders = Order.objects.filter(company_id__in=company_ids).delete()
    stdout.write(f"   Deleted orders: {deleted_orders}\n")

    # Customers (CompanyUser + Customer profile)
    from apps.accounts.models import Customer
    deleted_customers = Customer.objects.filter(company_id__in=company_ids).delete()
    stdout.write(f"   Deleted customers: {deleted_customers}\n")

    # Technicians (cascade deletes Technician profile, skills)
    tech_users = User.objects.filter(
        company_id__in=company_ids,
        role="TECHNICIAN",
    )
    for u in tech_users:
        try:
            u.technician_profile.delete()
        except Exception:
            pass
    deleted_techs = tech_users.delete()
    stdout.write(f"   Deleted technician users: {deleted_techs}\n")

    # Operators
    deleted_ops = User.objects.filter(
        company_id__in=company_ids,
        role="COMPANY_STAFF",
    ).delete()
    stdout.write(f"   Deleted operator users: {deleted_ops}\n")

    # Admins
    deleted_admins = User.objects.filter(
        company_id__in=company_ids,
        role="COMPANY_ADMIN",
    ).delete()
    stdout.write(f"   Deleted admin users: {deleted_admins}\n")

    # Merchant profiles + change requests
    CompanyMerchantProfileChangeRequest.objects.filter(company_id__in=company_ids).delete()
    CompanyMerchantProfile.objects.filter(company_id__in=company_ids).delete()

    # Service categories + subcategories
    CompanyServiceCategory.objects.filter(company_id__in=company_ids).delete()

    # Financial policies
    CompanyFinancialPolicy.objects.filter(company_id__in=company_ids).delete()

    # Companies themselves
    deleted_companies = companies.delete()
    stdout.write(f"   Deleted companies: {deleted_companies}\n")

    # Platform owner
    deleted_po = User.objects.filter(username="platform_owner").delete()
    stdout.write(f"   Deleted platform_owner: {deleted_po}\n")

    stdout.write("   ✓ Reset complete.\n\n")


# ---------------------------------------------------------------------------
# Main seed functions
# ---------------------------------------------------------------------------

def _seed_platform_owner(stdout):
    from apps.accounts.models import UserRole

    user, created = _make_user(
        username="platform_owner",
        password=DEMO_PASSWORD,
        role=UserRole.PLATFORM_OWNER,
        first_name="مالک",
        last_name="پلتفرم",
        phone="09100000000",
    )
    action = "created" if created else "updated"
    stdout.write(f"  Platform owner {action}: platform_owner\n")
    return user


def _seed_company(company_def, stdout):
    from apps.tenants.models import Company
    from apps.sms.provisioning import provision_company_communication_defaults

    company, created = Company.objects.update_or_create(
        code=company_def["code"],
        defaults={
            "name": company_def["name"],
            "slug": company_def["code"],
            "is_active": True,
            "phone": "",
            "email": "",
            "address": "",
        },
    )
    action = "created" if created else "updated"
    stdout.write(f"  Company {action}: {company.code}\n")

    # Provision SMS templates (idempotent)
    try:
        provision_company_communication_defaults(company)
    except Exception as e:
        stdout.write(f"  [warn] SMS provisioning for {company.code}: {e}\n")

    # Ensure merchant profile exists
    try:
        from apps.tenants.services_merchant_profile import MerchantProfileService
        MerchantProfileService.get_or_create(company)
    except Exception as e:
        stdout.write(f"  [warn] Merchant profile init for {company.code}: {e}\n")

    return company


def _seed_company_admin(company, stdout):
    from apps.accounts.models import UserRole

    username = f"{company.code}_admin"
    user, created = _make_user(
        username=username,
        password=DEMO_PASSWORD,
        role=UserRole.COMPANY_ADMIN,
        company=company,
        first_name="مدیر",
        last_name=company.name,
        phone=_phone_for_company(company.code, "000"),
    )
    action = "created" if created else "updated"
    stdout.write(f"  Admin {action}: {username}\n")
    return user


def _seed_operator(company, stdout):
    from apps.accounts.models import UserRole, OperatorPermission

    username = f"{company.code}_operator"
    user, created = _make_user(
        username=username,
        password=DEMO_PASSWORD,
        role=UserRole.COMPANY_STAFF,
        company=company,
        first_name="اپراتور",
        last_name=company.name,
        phone=_phone_for_company(company.code, "001"),
    )
    action = "created" if created else "updated"
    stdout.write(f"  Operator {action}: {username}\n")

    # Grant order-related permissions
    for key in OPERATOR_ORDER_PERMISSIONS:
        OperatorPermission.objects.update_or_create(
            company=company,
            operator=user,
            permission_key=key,
            defaults={"is_allowed": True},
        )
    stdout.write(f"    → {len(OPERATOR_ORDER_PERMISSIONS)} order permissions granted\n")
    return user


def _seed_technicians(company, stdout):
    from apps.accounts.models import UserRole, Technician

    tech_defs = TECHNICIAN_DATA[company.code]
    technicians = []

    for i, td in enumerate(tech_defs, start=1):
        user, created = _make_user(
            username=td["username"],
            password=DEMO_PASSWORD,
            role=UserRole.TECHNICIAN,
            company=company,
            first_name=td["first_name"],
            last_name=td["last_name"],
            phone=td["phone"],
        )

        wage = td["wage"]
        tech, t_created = Technician.objects.update_or_create(
            user=user,
            defaults={
                "company": company,
                "is_available": True,
                "service_wage_percent": wage,
                "goods_wage_percent": wage,
                "travel_wage_percent": wage,
                "notes": f"تکنسین دمو {i}",
            },
        )

        # Financial verification variety
        if i == 1:
            # tech1: VERIFIED with SHABA and sub_merchant_id
            tech.shaba_number = f"IR{td['phone'][1:]}000000"
            tech.shaba_verified = True
            tech.shaba_verified_at = timezone.now() - timedelta(days=30)
            tech.sub_merchant_id = f"SUB-{company.code.upper()}-{i:03d}"
            tech.financial_verification_status = Technician.FinancialVerificationStatus.VERIFIED
            tech.verification_note = "تأیید شده توسط پلتفرم"
        elif i == 2:
            # tech2: PENDING with SHABA, no sub_merchant_id
            tech.shaba_number = f"IR{td['phone'][1:]}000000"
            tech.shaba_verified = False
            tech.sub_merchant_id = ""
            tech.financial_verification_status = Technician.FinancialVerificationStatus.PENDING
        else:
            # tech3: NOT_SUBMITTED
            tech.shaba_number = ""
            tech.shaba_verified = False
            tech.sub_merchant_id = ""
            tech.financial_verification_status = Technician.FinancialVerificationStatus.NOT_SUBMITTED

        tech.save()

        action = "created" if t_created else "updated"
        stdout.write(f"  Technician {action}: {td['username']} ({wage}% wage, {tech.financial_verification_status})\n")
        technicians.append(tech)

    return technicians


def _seed_categories(company, stdout):
    from apps.tenants.models import CompanyServiceCategory, CompanyServiceSubCategory

    categories = []
    for i, cat_def in enumerate(CATEGORIES, start=1):
        cat, created = CompanyServiceCategory.objects.update_or_create(
            company=company,
            title=cat_def["title"],
            defaults={
                "description": "",
                "is_active": True,
                "sort_order": i * 10,
            },
        )
        action = "created" if created else "updated"
        stdout.write(f"  Category {action}: {cat.title}\n")

        for j, item_def in enumerate(cat_def["items"], start=1):
            subcat, s_created = CompanyServiceSubCategory.objects.update_or_create(
                company=company,
                category=cat,
                title=item_def["title"],
                defaults={
                    "description": "",
                    "base_price": item_def["base_price"],
                    "is_active": True,
                    "sort_order": j * 10,
                },
            )
            s_action = "created" if s_created else "updated"
            stdout.write(f"    SubCategory {s_action}: {subcat.title} ({subcat.base_price:,} ریال)\n")

        categories.append(cat)

    return categories


def _seed_customers(company, stdout):
    from apps.accounts.models import Customer

    customers = []
    for cd in CUSTOMER_DATA:
        phone = _phone_for_company(company.code, cd["phone_suffix"])
        customer, created = Customer.objects.update_or_create(
            company=company,
            phone=phone,
            defaults={
                "first_name": cd["first_name"],
                "last_name": cd["last_name"],
                "address": cd["address"],
                "email": "",
                "notes": "",
            },
        )
        customers.append(customer)

    stdout.write(f"  Customers: {len(customers)} seeded for {company.code}\n")
    return customers


def _seed_orders(company, customers, technicians, categories, stdout):
    from apps.orders.models import Order

    # Avoid DONE — it auto-creates a draft Invoice
    statuses = ORDER_STATUSES[:]  # 10 statuses for 10 orders

    created_count = 0
    updated_count = 0

    for idx in range(10):
        customer = customers[idx % len(customers)]
        status = statuses[idx]
        description = ORDER_DESCRIPTIONS[idx]
        category = categories[idx % len(categories)]

        # Assign technician to some orders, leave some unassigned
        if idx < 7:
            technician = technicians[idx % len(technicians)]
        else:
            technician = None

        service_date = date.today() - timedelta(days=random.randint(0, 30)) + timedelta(days=idx)

        # Use a stable title to allow idempotent update_or_create
        title = f"سفارش دمو {idx + 1} — {company.code.upper()}"

        order, created = Order.objects.update_or_create(
            company=company,
            title=title,
            defaults={
                "customer": customer,
                "customer_name": f"{customer.first_name} {customer.last_name}",
                "customer_phone": customer.phone,
                "technician": technician,
                "service_category": category,
                "description": description,
                "address": customer.address,
                "service_date": service_date,
                "priority": "NORMAL",
                "status": status,
                "price_estimate": (idx + 1) * 500000,
                "final_price": (idx + 1) * 500000 if status in ("IN_PROGRESS", "WAITING") else 0,
                "notes": "",
            },
        )

        if created:
            created_count += 1
        else:
            updated_count += 1

    stdout.write(f"  Orders: {created_count} created, {updated_count} updated for {company.code}\n")


def _seed_merchant_profile(company, stdout):
    from apps.tenants.models import CompanyMerchantProfile
    from apps.tenants.services_merchant_profile import MerchantProfileService

    profile = MerchantProfileService.get_or_create(company)
    variant = MERCHANT_PROFILE_VARIANTS.get(company.code, "not_submitted")

    if variant == "approved":
        profile.status = CompanyMerchantProfile.Status.APPROVED
        profile.company_type = "legal_entity"
        profile.legal_company_name = f"شرکت دمو {company.name}"
        profile.national_id = "1234567890"
        profile.economic_code = "9876543210"
        profile.registration_number = "123456"
        profile.postal_code = "1234567890"
        profile.registered_address = "تهران، خیابان ولیعصر، پلاک ۱"
        profile.company_phone = "02112345678"
        profile.owner_full_name = "مدیرعامل دمو"
        profile.owner_national_code = "0012345678"
        profile.owner_mobile = "09120000000"
        profile.bank_name = "بانک ملت"
        profile.account_holder_name = f"شرکت {company.name}"
        profile.shaba_number = "IR120570028080010608002001"
        profile.bank_account_number = "1234567890"
        profile.bank_card_number = "6104337812345678"
        profile.submitted_at = timezone.now() - timedelta(days=10)
        profile.reviewed_at = timezone.now() - timedelta(days=5)
        profile.review_note = "مدارک بررسی و تأیید شد."
        profile.save()
        stdout.write(f"  Merchant profile: APPROVED for {company.code}\n")

    elif variant == "under_review":
        profile.status = CompanyMerchantProfile.Status.UNDER_REVIEW
        profile.legal_company_name = f"شرکت دمو {company.name}"
        profile.owner_full_name = "مدیرعامل دمو"
        profile.owner_mobile = "09130000000"
        profile.bank_name = "بانک تجارت"
        profile.account_holder_name = f"شرکت {company.name}"
        profile.shaba_number = "IR820570028080010608002002"
        profile.postal_code = "9876543210"
        profile.registered_address = "تهران، خیابان انقلاب"
        profile.company_phone = "02198765432"
        profile.owner_national_code = "0098765432"
        profile.submitted_at = timezone.now() - timedelta(days=3)
        profile.save()
        stdout.write(f"  Merchant profile: UNDER_REVIEW for {company.code}\n")

    else:
        # not_submitted — leave as is
        stdout.write(f"  Merchant profile: NOT_SUBMITTED for {company.code}\n")


def _seed_financial_policy(company, stdout):
    from apps.tenants.models import CompanyFinancialPolicy

    policy_def = FINANCIAL_POLICY.get(company.code)
    if not policy_def:
        return

    policy, created = CompanyFinancialPolicy.objects.update_or_create(
        company=company,
        defaults={
            "payout_strategy": policy_def["payout_strategy"],
            "platform_fee_percent": policy_def["platform_fee_percent"],
        },
    )
    action = "created" if created else "updated"
    stdout.write(
        f"  Financial policy {action}: {policy_def['payout_strategy']} / "
        f"fee={policy_def['platform_fee_percent']}% for {company.code}\n"
    )


# ---------------------------------------------------------------------------
# Command
# ---------------------------------------------------------------------------

class Command(BaseCommand):
    help = "Seed full demo/test data for local development. Use --reset to wipe and re-seed."

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            default=False,
            help="Delete existing demo data and re-seed from scratch.",
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "\n======================================================\n"
            "  seed_full_demo — LOCAL DEVELOPMENT ONLY\n"
            "======================================================\n"
        ))

        if options["reset"]:
            self.stdout.write(self.style.ERROR(
                "⚠️  --reset flag detected. Deleting demo data...\n"
            ))
            with transaction.atomic():
                _reset_demo_data(self.stdout)

        self.stdout.write(self.style.SUCCESS("Seeding demo data...\n"))

        with transaction.atomic():
            # 1. Platform owner
            self.stdout.write("\n--- Platform Owner ---\n")
            _seed_platform_owner(self.stdout)

            # 2. Companies + all tenant data
            all_companies = []
            for cdef in COMPANY_DEFS:
                self.stdout.write(f"\n--- Company: {cdef['code']} ---\n")
                company = _seed_company(cdef, self.stdout)
                all_companies.append(company)

                _seed_company_admin(company, self.stdout)
                _seed_operator(company, self.stdout)
                technicians = _seed_technicians(company, self.stdout)
                categories = _seed_categories(company, self.stdout)
                customers = _seed_customers(company, self.stdout)
                _seed_orders(company, customers, technicians, categories, self.stdout)
                _seed_merchant_profile(company, self.stdout)
                _seed_financial_policy(company, self.stdout)

        self._print_credentials()

    def _print_credentials(self):
        self.stdout.write(self.style.SUCCESS(
            "\n\n======================================================\n"
            "  DEMO CREDENTIALS — password for all: 123456789\n"
            "======================================================\n"
        ))

        rows = [
            ("پلتفرم", "PLATFORM_OWNER", "platform_owner", "/login/"),
            ("n54",    "COMPANY_ADMIN",  "n54_admin",       "/n54/admin/"),
            ("n54",    "COMPANY_STAFF",  "n54_operator",    "/n54/admin/"),
            ("n54",    "TECHNICIAN",     "n54_tech1",       "/n54/tech/"),
            ("n54",    "TECHNICIAN",     "n54_tech2",       "/n54/tech/"),
            ("n54",    "TECHNICIAN",     "n54_tech3",       "/n54/tech/"),
            ("rayan",  "COMPANY_ADMIN",  "rayan_admin",     "/rayan/admin/"),
            ("rayan",  "COMPANY_STAFF",  "rayan_operator",  "/rayan/admin/"),
            ("rayan",  "TECHNICIAN",     "rayan_tech1",     "/rayan/tech/"),
            ("rayan",  "TECHNICIAN",     "rayan_tech2",     "/rayan/tech/"),
            ("rayan",  "TECHNICIAN",     "rayan_tech3",     "/rayan/tech/"),
            ("sepid",  "COMPANY_ADMIN",  "sepid_admin",     "/sepid/admin/"),
            ("sepid",  "COMPANY_STAFF",  "sepid_operator",  "/sepid/admin/"),
            ("sepid",  "TECHNICIAN",     "sepid_tech1",     "/sepid/tech/"),
            ("sepid",  "TECHNICIAN",     "sepid_tech2",     "/sepid/tech/"),
            ("sepid",  "TECHNICIAN",     "sepid_tech3",     "/sepid/tech/"),
        ]

        col_widths = [8, 16, 18, 6, 30]
        header = f"{'شرکت':<8} {'نقش':<16} {'نام کاربری':<18} {'رمز':<6} {'آدرس'}"
        self.stdout.write("-" * 70 + "\n")
        self.stdout.write(header + "\n")
        self.stdout.write("-" * 70 + "\n")
        for company, role, username, url in rows:
            self.stdout.write(f"{company:<8} {role:<16} {username:<18} {'123456789':<12} {url}\n")
        self.stdout.write("-" * 70 + "\n")

        self.stdout.write(self.style.SUCCESS(
            "\n📋  Manual test URLs:\n"
            "  /login/\n"
            "  /owner-platform/dashboard/\n"
            "  /owner-platform/companies/\n"
            "  /owner-platform/merchant-profiles/\n"
            "  /owner-platform/technician-financial-verifications/\n"
            "  /owner-platform/payment-split-snapshots/\n"
            "  /n54/login/\n"
            "  /n54/admin/\n"
            "  /n54/admin/orders/\n"
            "  /n54/admin/technicians/\n"
            "  /n54/admin/payment/merchant-profile/\n"
            "  /n54/admin/payments/split-snapshots/\n"
            "  /rayan/admin/\n"
            "  /sepid/admin/\n"
            "\n"
            "✅  Seed complete.\n"
        ))
