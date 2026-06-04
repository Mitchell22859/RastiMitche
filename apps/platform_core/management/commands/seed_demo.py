"""
Management command: seed_demo

Creates a complete demo tenant with sample data for local development and demos.

Usage:
    python manage.py seed_demo

Idempotent: Running multiple times will not duplicate records.
"""
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CompanyUser, Customer, Technician, TechnicianSkill, TechnicianCategorySkill, UserRole
from apps.invoices.models import Invoice, InvoiceItem
from apps.notifications.models import Notification
from apps.notifications.services import NotificationCreateService
from apps.orders.models import Order, OrderItemDefinition, OrderStatusLog
from apps.payments.models import Payment, PaymentGateway
from apps.sms.models import SMSOutbox, SMSProvider
from apps.tenants.models import Company, CompanyGalleryImage, CompanyPage, CompanyService, CompanyServiceCategory


class Command(BaseCommand):
    help = "Create demo tenant with sample data for local development."

    COMPANY_CODE = "n54"
    PASSWORD = "password123"

    @transaction.atomic
    def handle(self, *args, **options):
        self.stdout.write(self.style.MIGRATE_HEADING("Seeding demo data..."))

        # 1. Platform Owner
        platform_owner = self._create_platform_owner()

        # 2. Company
        company = self._create_company()

        # 3. Company Page
        self._create_company_page(company)

        # 4. Company Services
        services = self._create_services(company)

        # 4b. Service Categories
        categories = self._create_categories(company)
        self._create_order_item_definitions(company, categories)

        # 5. Users
        admin = self._create_admin(company)
        tech_user, technician = self._create_technician(company)
        cust_user, customer = self._create_customer(company)

        # 6. Technician Skills
        self._create_skills(company, technician)
        self._create_category_skills(technician, categories)

        # 7. Orders
        orders = self._create_orders(company, customer, technician, admin)

        # 7b. Assign categories to orders
        self._assign_categories_to_orders(company, orders, categories)

        # 8. Invoices
        invoices = self._create_invoices(company, customer, orders)

        # 9. Payment Gateway + Sample Payment
        self._create_payment_gateway(company)

        # 10. SMS Provider + Outbox samples
        self._create_sms_samples(company, customer)

        # 11. Notifications
        self._create_notifications(company, admin, cust_user, orders)

        # Print summary
        self._print_summary(company)

    def _create_platform_owner(self) -> CompanyUser:
        user, created = CompanyUser.objects.get_or_create(
            username="platform_owner",
            defaults={
                "phone": "09100000001",
                "role": UserRole.PLATFORM_OWNER,
                "is_staff": True,
                "is_superuser": True,
                "first_name": "Platform",
                "last_name": "Owner",
            },
        )
        if created:
            user.set_password(self.PASSWORD)
            user.save()
            self.stdout.write(f"  Created platform owner: platform_owner")
        else:
            self.stdout.write(f"  Platform owner already exists: platform_owner")
        return user

    def _create_company(self) -> Company:
        company, created = Company.objects.get_or_create(
            code=self.COMPANY_CODE,
            defaults={
                "name": "N54 Service",
                "slug": "n54-service",
                "is_active": True,
                "email": "info@n54service.ir",
                "phone": "02112345678",
                "address": "Tehran, Vali-Asr St.",
            },
        )
        if created:
            self.stdout.write(f"  Created company: {company.name} ({company.code})")
        else:
            self.stdout.write(f"  Company already exists: {company.name}")
        return company

    def _create_company_page(self, company: Company) -> CompanyPage:
        page, created = CompanyPage.objects.get_or_create(
            company=company,
            defaults={
                "title": "N54 Service - Professional Home Services",
                "intro_text": "We provide professional plumbing, electrical, and HVAC services across Tehran.",
                "contact_phone": "02112345678",
                "contact_email": "info@n54service.ir",
                "address": "Tehran, Vali-Asr St, Tower 54",
                "working_hours": "Saturday-Thursday 8:00-20:00",
                "is_request_form_enabled": True,
                "is_published": True,
            },
        )
        if created:
            self.stdout.write(f"  Created company page")
        return page

    def _create_services(self, company: Company) -> list[CompanyService]:
        services_data = [
            {"title": "Plumbing", "description": "Pipe repair, faucet installation, water heater service.", "base_price": 500000},
            {"title": "Electrical", "description": "Wiring, outlet installation, panel repair.", "base_price": 400000},
            {"title": "HVAC", "description": "AC installation, heating system repair.", "base_price": 800000},
            {"title": "Painting", "description": "Interior and exterior painting.", "base_price": 300000},
        ]
        services = []
        for data in services_data:
            svc, created = CompanyService.objects.get_or_create(
                company=company,
                title=data["title"],
                defaults={"description": data["description"], "base_price": data["base_price"], "is_active": True},
            )
            services.append(svc)
        self.stdout.write(f"  Services: {len(services)} total")
        return services

    def _create_categories(self, company: Company) -> dict:
        """Create service categories only. Subcategory is intentionally disabled."""
        category_titles = [
            "ظ†طµط¨ ظ¾ع©غŒط¬ ظˆ ط±ط§ط¯غŒط§طھظˆط±",
            "ظ„ظˆظ„ظ‡â€Œع©ط´غŒ",
            "ط¨ط±ظ‚â€Œع©ط§ط±غŒ",
            "ظ†ظ‚ط§ط´غŒ",
            "طھظ‡ظˆغŒظ‡ ظˆ ع©ظˆظ„ط±",
        ]
        result = {}
        for sort_order, cat_title in enumerate(category_titles):
            cat, _ = CompanyServiceCategory.objects.get_or_create(
                company=company,
                title=cat_title,
                defaults={"is_active": True, "sort_order": sort_order},
            )
            result[cat_title] = cat

        self.stdout.write(f"  Categories: {len(result)} total")
        return result

    def _create_order_item_definitions(self, company: Company, categories: dict) -> None:
        """Create Rasti-style dynamic order items for the main service category."""
        category = categories.get("ظ†طµط¨ ظ¾ع©غŒط¬ ظˆ ط±ط§ط¯غŒط§طھظˆط±")
        if not category:
            return
        items = [
            ("ظ¾ع©غŒط¬ ط§غŒط±ط§ظ†", OrderItemDefinition.Kind.NUMBER),
            ("ظ¾ع©غŒط¬ ط¨ظˆطھط§ظ†", OrderItemDefinition.Kind.NUMBER),
            ("ظ¾ع©غŒط¬ ط®ط§ط±ط¬غŒ", OrderItemDefinition.Kind.NUMBER),
            ("ط±ط§ط¯غŒط§طھظˆط±", OrderItemDefinition.Kind.NUMBER),
            ("ع©ظˆظ¾ظ„ ط¨ظ†ط¯غŒ", OrderItemDefinition.Kind.NUMBER),
        ]
        for index, (title, kind) in enumerate(items):
            OrderItemDefinition.objects.get_or_create(
                company=company,
                category=category,
                title=title,
                defaults={"kind": kind, "is_active": True, "sort_order": index},
            )
        self.stdout.write("  Order item definitions: Rasti package/radiator items")

    def _create_category_skills(self, technician: Technician, categories: dict) -> None:
        """Connect demo technician to all categories with priority 1."""
        for category in categories.values():
            TechnicianCategorySkill.objects.get_or_create(
                technician=technician,
                category=category,
                defaults={"priority": TechnicianCategorySkill.Priority.P1},
            )
        self.stdout.write("  Technician category priorities: P1 for demo technician")

    def _create_admin(self, company: Company) -> CompanyUser:
        user, created = CompanyUser.objects.get_or_create(
            username="n54_admin",
            defaults={
                "phone": "09100000002",
                "company": company,
                "role": UserRole.COMPANY_ADMIN,
                "first_name": "Admin",
                "last_name": "N54",
            },
        )
        if created:
            user.set_password(self.PASSWORD)
            user.save()
            self.stdout.write(f"  Created admin: n54_admin")
        return user

    def _create_technician(self, company: Company) -> tuple[CompanyUser, Technician]:
        user, created = CompanyUser.objects.get_or_create(
            username="n54_tech",
            defaults={
                "phone": "09100000003",
                "company": company,
                "role": UserRole.TECHNICIAN,
                "first_name": "Ali",
                "last_name": "Technician",
            },
        )
        if created:
            user.set_password(self.PASSWORD)
            user.save()
            self.stdout.write(f"  Created technician user: n54_tech")

        technician, _ = Technician.objects.get_or_create(
            user=user,
            defaults={"company": company, "is_available": True, "rating": 4.5},
        )
        return user, technician

    def _create_customer(self, company: Company) -> tuple[CompanyUser, Customer]:
        user, created = CompanyUser.objects.get_or_create(
            username="n54_customer",
            defaults={
                "phone": "09100000004",
                "company": company,
                "role": UserRole.CUSTOMER,
                "first_name": "Sara",
                "last_name": "Customer",
            },
        )
        if created:
            user.set_password(self.PASSWORD)
            user.save()
            self.stdout.write(f"  Created customer user: n54_customer")

        customer, _ = Customer.objects.get_or_create(
            company=company,
            phone="09100000004",
            defaults={
                "user": user,
                "first_name": "Sara",
                "last_name": "Customer",
                "email": "sara@example.com",
                "address": "Tehran, Jordan Blvd",
            },
        )
        return user, customer

    def _create_skills(self, company: Company, technician: Technician) -> None:
        skills = ["plumbing", "electrical", "hvac"]
        for skill_name in skills:
            TechnicianSkill.objects.get_or_create(
                company=company,
                technician=technician,
                name=skill_name,
                defaults={"level": "expert"},
            )
        self.stdout.write(f"  Technician skills: {', '.join(skills)}")

    def _create_orders(self, company, customer, technician, admin) -> dict:
        orders = {}

        # NEW order
        order_new, created = Order.objects.get_or_create(
            company=company,
            title="Fix kitchen faucet",
            customer=customer,
            defaults={
                "description": "Kitchen faucet is leaking and needs replacement.",
                "address": "Tehran, Jordan Blvd, Unit 5",
                "status": Order.Status.NEW,
                "priority": Order.Priority.NORMAL,
                "price_estimate": 500000,
                "required_skill": "plumbing",
            },
        )
        orders["new"] = order_new

        # IN_PROGRESS order
        order_prog, created = Order.objects.get_or_create(
            company=company,
            title="Electrical panel upgrade",
            customer=customer,
            defaults={
                "description": "Upgrade main electrical panel from 100A to 200A.",
                "address": "Tehran, Jordan Blvd, Unit 5",
                "status": Order.Status.IN_PROGRESS,
                "priority": Order.Priority.HIGH,
                "price_estimate": 2000000,
                "required_skill": "electrical",
                "technician": technician,
            },
        )
        orders["in_progress"] = order_prog

        # DONE order
        order_done, created = Order.objects.get_or_create(
            company=company,
            title="Install split AC unit",
            customer=customer,
            defaults={
                "description": "Install new split AC in bedroom.",
                "address": "Tehran, Jordan Blvd, Unit 5",
                "status": Order.Status.DONE,
                "priority": Order.Priority.NORMAL,
                "price_estimate": 3000000,
                "final_price": 3200000,
                "required_skill": "hvac",
                "technician": technician,
                "completed_at": timezone.now(),
            },
        )
        orders["done"] = order_done

        self.stdout.write(f"  Orders: NEW, IN_PROGRESS, DONE")
        return orders

    def _assign_categories_to_orders(self, company, orders, categories) -> None:
        """Assign categories to demo orders. Subcategory is intentionally disabled."""
        if not categories:
            return
        plumbing_cat = categories.get("ظ„ظˆظ„ظ‡â€Œع©ط´غŒ")
        electrical_cat = categories.get("ط¨ط±ظ‚â€Œع©ط§ط±غŒ")
        hvac_cat = categories.get("طھظ‡ظˆغŒظ‡ ظˆ ع©ظˆظ„ط±")

        if plumbing_cat and orders.get("new") and not orders["new"].service_category:
            orders["new"].service_category = plumbing_cat
            orders["new"].service_subcategory = None
            orders["new"].save(update_fields=["service_category", "service_subcategory"])

        if electrical_cat and orders.get("in_progress") and not orders["in_progress"].service_category:
            orders["in_progress"].service_category = electrical_cat
            orders["in_progress"].service_subcategory = None
            orders["in_progress"].save(update_fields=["service_category", "service_subcategory"])

        if hvac_cat and orders.get("done") and not orders["done"].service_category:
            orders["done"].service_category = hvac_cat
            orders["done"].service_subcategory = None
            orders["done"].save(update_fields=["service_category", "service_subcategory"])

    def _create_invoices(self, company, customer, orders) -> dict:
        invoices = {}

        # ISSUED invoice
        inv_issued, created = Invoice.objects.get_or_create(
            company=company,
            invoice_number="INV-N54-00001",
            defaults={
                "customer": customer,
                "order": orders["in_progress"],
                "status": Invoice.Status.ISSUED,
                "subtotal": 2000000,
                "total_amount": 2000000,
                "issued_at": timezone.now(),
            },
        )
        if created:
            InvoiceItem.objects.get_or_create(
                company=company,
                invoice=inv_issued,
                description="Electrical panel upgrade",
                defaults={"quantity": 1, "unit_price": 2000000, "total_price": 2000000},
            )
        invoices["issued"] = inv_issued

        # PAID invoice
        inv_paid, created = Invoice.objects.get_or_create(
            company=company,
            invoice_number="INV-N54-00002",
            defaults={
                "customer": customer,
                "order": orders["done"],
                "status": Invoice.Status.PAID,
                "subtotal": 3200000,
                "total_amount": 3200000,
                "issued_at": timezone.now(),
                "paid_at": timezone.now(),
            },
        )
        if created:
            InvoiceItem.objects.get_or_create(
                company=company,
                invoice=inv_paid,
                description="Split AC installation",
                defaults={"quantity": 1, "unit_price": 3200000, "total_price": 3200000},
            )
        invoices["paid"] = inv_paid

        self.stdout.write(f"  Invoices: ISSUED, PAID")
        return invoices

    def _create_payment_gateway(self, company) -> None:
        PaymentGateway.objects.get_or_create(
            company=company,
            gateway_type=PaymentGateway.GatewayType.FAKE,
            defaults={
                "name": "Test Gateway (Fake)",
                "merchant_id": "demo_merchant",
                "api_key": "demo_api_key",
                "is_active": True,
                "is_default": True,
            },
        )
        self.stdout.write(f"  Payment gateway: Fake (for testing)")

    def _create_sms_samples(self, company, customer) -> None:
        provider, _ = SMSProvider.objects.get_or_create(
            company=company,
            provider_type=SMSProvider.ProviderType.FAKE,
            defaults={
                "name": "Demo SMS Provider",
                "api_key": "demo_sms_key",
                "sender_number": "30001234",
                "is_active": True,
            },
        )

        # Sample sent SMS
        SMSOutbox.objects.get_or_create(
            company=company,
            phone_number=customer.phone,
            message="Your order has been registered. Tracking: #1",
            defaults={
                "provider": provider,
                "status": SMSOutbox.Status.SENT,
                "provider_message_id": "FAKE-demo001",
                "sent_at": timezone.now(),
            },
        )
        self.stdout.write(f"  SMS: provider + sample outbox")

    def _create_notifications(self, company, admin, cust_user, orders) -> None:
        # Only create if none exist for this company
        if Notification.objects.filter(company=company).exists():
            self.stdout.write(f"  Notifications already exist")
            return

        NotificationCreateService.create(
            company=company,
            recipient=admin,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="New Order: Fix kitchen faucet",
            message="A new service request has been submitted.",
            related_order=orders["new"],
        )
        NotificationCreateService.create(
            company=company,
            recipient=cust_user,
            notification_type=Notification.NotificationType.ORDER_ACCEPTED,
            title="Order Accepted",
            message="A technician has been assigned to your electrical panel upgrade.",
            related_order=orders["in_progress"],
        )
        NotificationCreateService.create(
            company=company,
            recipient=cust_user,
            notification_type=Notification.NotificationType.ORDER_COMPLETED,
            title="Order Completed",
            message="Your AC installation is complete!",
            related_order=orders["done"],
        )
        NotificationCreateService.create(
            company=company,
            recipient=cust_user,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
            title="Payment Confirmed",
            message="Payment for invoice INV-N54-00002 confirmed.",
        )
        self.stdout.write(f"  Notifications: 4 created")

    def _print_summary(self, company: Company) -> None:
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write(self.style.SUCCESS("  DEMO DATA CREATED SUCCESSFULLY"))
        self.stdout.write(self.style.SUCCESS("=" * 60))
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("  Login URLs:"))
        self.stdout.write(f"    Platform:   http://localhost:8000/loginlogin/")
        self.stdout.write(f"    Company:    http://localhost:8000/{company.code}/login/")
        self.stdout.write(f"    Public:     http://localhost:8000/{company.code}/")
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("  Credentials (password: password123):"))
        self.stdout.write(f"    Platform Owner:  platform_owner")
        self.stdout.write(f"    Company Admin:   n54_admin")
        self.stdout.write(f"    Technician:      n54_tech")
        self.stdout.write(f"    Customer:        n54_customer")
        self.stdout.write("")
        self.stdout.write(self.style.MIGRATE_HEADING("  Key URLs:"))
        self.stdout.write(f"    Admin Dashboard: http://localhost:8000/{company.code}/admin/")
        self.stdout.write(f"    Orders:          http://localhost:8000/{company.code}/tech/orders/available/")
        self.stdout.write(f"    Invoices:        http://localhost:8000/{company.code}/invoices/")
        self.stdout.write(f"    API Orders:      http://localhost:8000/api/{company.code}/orders/")
        self.stdout.write(f"    API Services:    http://localhost:8000/api/{company.code}/services/")
        self.stdout.write(f"    Health:          http://localhost:8000/health/")
        self.stdout.write("")

