
from __future__ import annotations

from decimal import Decimal
from datetime import timedelta, time
import uuid

from django.apps import apps
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone


COMPANY_DEFS = [
    ("n54", "شرکت نمونه ۵۴"),
    ("rayan", "شرکت خدمات رایان"),
    ("sepid", "شرکت نظافت سپید"),
]

CATEGORY_NAMES = ["نظافت منزل", "قالیشویی و مبل", "خدمات اداری"]

EVENT_KEYS = [
    "order_created_admin",
    "order_available_technician",
    "order_assigned_technician",
    "order_accepted_customer",
    "order_completed_customer",
    "order_cancel_requested_admin",
    "order_cancel_approved_technician",
    "order_cancel_rejected_technician",
    "invoice_issued_customer",
    "payment_success_customer",
    "payment_failed_customer",
    "survey_request_customer",
]

PLATFORM_EVENT_KEYS = [
    "sms_credit_low_admin",
    "sms_credit_empty_admin",
    "subscription_expiring_admin",
    "subscription_expired_admin",
    "platform_payment_success_admin",
]

# Permission keys must match the url_name values resolved by OperatorPermissionMiddleware.
# The middleware calls django.urls.resolve(request.path_info).url_name to determine the key.
# AUTO_ALLOWED keys (home, admin_home, admin_dashboard) are always granted.
#
# NOTE: "list" is ambiguous — it matches both notifications:list and reports:list.
# For full operators this is acceptable (they should see both).
# For limited operators we exclude it to avoid unintended report access.
OPERATOR_FULL_KEYS = [
    "home",                             # dashboard (also auto-allowed)
    "admin_orders",                     # order list
    "admin_order_create",               # create order
    "admin_order_detail",               # view order detail
    "admin_order_edit",                 # edit order
    "admin_order_assign",               # assign technician
    "admin_cancel_request_approve",     # approve cancel request
    "admin_cancel_request_reject",      # reject cancel request
    "admin_order_return_to_cycle",      # return order to dispatch cycle
    "admin_invoices",                   # invoice list
    "admin_invoice_detail",             # view invoice detail
    "admin_invoice_create_from_order",  # create invoice from order
    "admin_invoice_edit",               # edit invoice
    "admin_invoice_cancel",             # cancel invoice
    "outbox",                           # SMS outbox root
    "outbox_list",                      # SMS outbox list
    "outbox_detail",                    # SMS outbox detail
    "template_list",                    # SMS templates
    "template_edit",                    # edit SMS template
    "template_toggle",                  # toggle SMS template
    "admin_communication_settings",     # notification event toggles
    "admin_notification_settings",      # notification settings
    "list",                             # notifications + reports (ambiguous, acceptable for full)
]
OPERATOR_LIMITED_KEYS = [
    "home",                             # dashboard (also auto-allowed)
    "admin_orders",                     # can view order list
    "admin_order_detail",               # can view order detail
    "admin_invoices",                   # can view invoice list
    "admin_invoice_detail",             # can view invoice detail
]


def model(app_label: str, model_name: str):
    try:
        return apps.get_model(app_label, model_name)
    except LookupError:
        return None


def has_field(model_cls, field_name: str) -> bool:
    if model_cls is None:
        return False
    return any(f.name == field_name for f in model_cls._meta.get_fields())


def set_fields(obj, **values):
    cls = obj.__class__
    for key, value in values.items():
        if has_field(cls, key):
            setattr(obj, key, value)
    return obj


def get_choices(model_cls, field_name: str) -> list[str]:
    try:
        field = model_cls._meta.get_field(field_name)
        return [str(choice[0]) for choice in (field.choices or [])]
    except Exception:
        return []


def pick_choice(model_cls, field_name: str, preferred: list[str], fallback: str = "") -> str:
    choices = get_choices(model_cls, field_name)
    for item in preferred:
        if item in choices:
            return item
    if choices:
        return choices[0]
    return fallback or (preferred[0] if preferred else "")


def save(obj):
    obj.save()
    return obj


def full_name(user) -> str:
    if not user:
        return ""
    try:
        return user.get_full_name()
    except Exception:
        return (getattr(user, "first_name", "") + " " + getattr(user, "last_name", "")).strip() or getattr(user, "username", "")


def normalize_role_value(role):
    """Convert readable seed role names to the real UserRole DB values."""
    try:
        from apps.accounts.models import UserRole
        role_map = {
            "platform_owner": UserRole.PLATFORM_OWNER,
            "company_admin": UserRole.COMPANY_ADMIN,
            "company_staff": UserRole.COMPANY_STAFF,
            "operator": UserRole.COMPANY_STAFF,
            "technician": UserRole.TECHNICIAN,
            "customer": UserRole.CUSTOMER,
            "PLATFORM_OWNER": UserRole.PLATFORM_OWNER,
            "COMPANY_ADMIN": UserRole.COMPANY_ADMIN,
            "COMPANY_STAFF": UserRole.COMPANY_STAFF,
            "TECHNICIAN": UserRole.TECHNICIAN,
            "CUSTOMER": UserRole.CUSTOMER,
        }
        return role_map.get(str(role), role_map.get(str(role).lower(), role))
    except Exception:
        fallback_map = {
            "platform_owner": "PLATFORM_OWNER",
            "company_admin": "COMPANY_ADMIN",
            "company_staff": "COMPANY_STAFF",
            "operator": "COMPANY_STAFF",
            "technician": "TECHNICIAN",
            "customer": "CUSTOMER",
        }
        return fallback_map.get(str(role).lower(), role)


def reset_or_create_user(User, *, company, username, role, phone, first_name, last_name, is_staff=False, is_superuser=False):
    user = User.objects.filter(username=username).first() or User(username=username)
    role_value = normalize_role_value(role)
    set_fields(
        user,
        company=company,
        role=role_value,
        phone=phone,
        email=f"{username}@demo.local",
        first_name=first_name,
        last_name=last_name,
        is_active=True,
        is_staff=is_staff,
        is_superuser=is_superuser,
    )
    user.password = make_password("123456")
    return save(user)


class Command(BaseCommand):
    help = "Reset and seed a complete demo database based on the real current models."

    def add_arguments(self, parser):
        parser.add_argument("--reset", action="store_true", help="Flush database before seeding.")
        parser.add_argument("--yes", action="store_true", help="Required with --reset.")
        parser.add_argument("--companies", type=int, default=3)
        parser.add_argument("--orders-per-company", type=int, default=7)
        parser.add_argument("--invoices-per-company", type=int, default=9)

    def handle(self, *args, **options):
        if options["reset"] and not options["yes"]:
            raise CommandError("Use --reset --yes to confirm database flush.")

        if options["reset"]:
            self.stdout.write(self.style.WARNING("Flushing database..."))
            call_command("flush", interactive=False, verbosity=0)

        with transaction.atomic():
            result = self.seed(options)

        self.print_summary(result)

    def seed(self, options):
        Company = model("tenants", "Company")
        CompanyPage = model("tenants", "CompanyPage")
        CompanySettings = model("tenants", "CompanySettings")
        CompanyService = model("tenants", "CompanyService")
        CompanyServiceCategory = model("tenants", "CompanyServiceCategory")
        CompanyServiceSubCategory = model("tenants", "CompanyServiceSubCategory")

        User = model("accounts", "CompanyUser")
        Technician = model("accounts", "Technician")
        TechnicianSkill = model("accounts", "TechnicianSkill")
        TechnicianCategorySkill = model("accounts", "TechnicianCategorySkill")
        Customer = model("accounts", "Customer")
        OperatorPermission = model("accounts", "OperatorPermission")

        Order = model("orders", "Order")
        OrderItemDefinition = model("orders", "OrderItemDefinition")
        OrderItemValue = model("orders", "OrderItemValue")
        OrderStatusLog = model("orders", "OrderStatusLog")

        Invoice = model("invoices", "Invoice")
        InvoiceItem = model("invoices", "InvoiceItem")

        Notification = model("notifications", "Notification")
        NotificationSetting = model("notifications", "NotificationSetting")
        NotificationEvent = model("notifications", "NotificationEvent")

        SMSProvider = model("sms", "SMSProvider")
        SMSTemplate = model("sms", "SMSTemplate")
        SMSOutbox = model("sms", "SMSOutbox")

        CompanySMSWallet = model("platform_core", "CompanySMSWallet")
        CompanySMSTransaction = model("platform_core", "CompanySMSTransaction")
        PlatformSMSOutbox = model("platform_core", "PlatformSMSOutbox")
        PlatformSMSProvider = model("platform_core", "PlatformSMSProvider")
        GlobalSMSPricingSetting = model("platform_core", "GlobalSMSPricingSetting")
        PlatformBillingInvoice = model("platform_core", "PlatformBillingInvoice")

        if not all([Company, User, Order, CompanyServiceCategory, CompanyServiceSubCategory]):
            raise CommandError("Required models are missing. Need Company, CompanyUser, Order, CompanyServiceCategory, CompanyServiceSubCategory.")

        counts = {
            "companies": 0,
            "platform_users": 0,
            "company_users": 0,
            "operator_permissions": 0,
            "technicians": 0,
            "technician_skills": 0,
            "customers": 0,
            "service_categories": 0,
            "service_subcategories": 0,
            "order_item_definitions": 0,
            "order_item_values": 0,
            "orders": 0,
            "order_logs": 0,
            "invoices": 0,
            "invoice_items": 0,
            "notification_settings": 0,
            "notifications": 0,
            "notification_events": 0,
            "sms_templates": 0,
            "company_sms_outbox": 0,
            "platform_sms_outbox": 0,
            "wallets": 0,
            "wallet_transactions": 0,
            "platform_billing_invoices": 0,
        }
        credentials = []

        # Platform owner and platform-level SMS config
        platform_owner = reset_or_create_user(
            User,
            company=None,
            username="platform_owner",
            role="platform_owner",
            phone="09000000000",
            first_name="مالک",
            last_name="پلتفرم",
            is_staff=True,
            is_superuser=True,
        )
        counts["platform_users"] += 1
        credentials.append(("platform owner", "platform_owner", "123456", "/owner-platform/"))

        if GlobalSMSPricingSetting:
            pricing = GlobalSMSPricingSetting.objects.first() or GlobalSMSPricingSetting()
            set_fields(pricing, characters_per_sms=60, price_per_sms_rial=520, updated_by=platform_owner)
            save(pricing)

        if PlatformSMSProvider:
            provider = PlatformSMSProvider.objects.first() or PlatformSMSProvider()
            set_fields(
                provider,
                name="Platform Fake SMS Provider",
                provider_type=pick_choice(PlatformSMSProvider, "provider_type", ["fake", "FAKE"], "fake"),
                api_key="test",
                sender_number="1000",
                is_active=True,
            )
            save(provider)

        selected_companies = COMPANY_DEFS[: options["companies"]]

        for ci, (code, company_name) in enumerate(selected_companies, start=1):
            company = self.create_company(Company, code, company_name, ci)
            counts["companies"] += 1

            if CompanyPage:
                page = CompanyPage.objects.filter(company=company).first() or CompanyPage(company=company)
                set_fields(
                    page,
                    title=f"صفحه خدمات {company_name}",
                    intro_text=f"معرفی خدمات {company_name} برای تست کامل سیستم.",
                    is_request_form_enabled=True,
                    contact_phone=f"021{ci}000000",
                    contact_email=f"info-{code}@demo.local",
                    address=f"تهران، آدرس تست شرکت {company_name}",
                    working_hours="شنبه تا پنجشنبه ۸ تا ۲۰",
                    is_published=True,
                )
                save(page)

            if CompanySettings:
                settings = CompanySettings.objects.filter(company=company).first() or CompanySettings(company=company)
                set_fields(
                    settings,
                    priority2_delay_minutes=15,
                    priority3_delay_minutes=30,
                    show_future_orders_to_technicians=True,
                    max_active_orders_per_technician=5,
                    auto_recycle_cancel_request=False,
                    respect_sms_template_time_window=True,
                )
                save(settings)

            admin = reset_or_create_user(User, company=company, username=f"{code}_admin", role="company_admin", phone=f"0910{ci}000001", first_name="مدیر", last_name=company_name)
            op_full = reset_or_create_user(User, company=company, username=f"{code}_operator_full", role="company_staff", phone=f"0910{ci}000002", first_name="اپراتور", last_name="کامل")
            op_limited = reset_or_create_user(User, company=company, username=f"{code}_operator_limited", role="company_staff", phone=f"0910{ci}000003", first_name="اپراتور", last_name="محدود")
            tech_user_1 = reset_or_create_user(User, company=company, username=f"{code}_tech_1", role="technician", phone=f"0912{ci}111111", first_name="تکنسین", last_name="یک")
            tech_user_2 = reset_or_create_user(User, company=company, username=f"{code}_tech_2", role="technician", phone=f"0912{ci}222222", first_name="تکنسین", last_name="دو")
            users = [admin, op_full, op_limited, tech_user_1, tech_user_2]
            counts["company_users"] += len(users)

            credentials += [
                (f"{code} admin", admin.username, "123456", f"/{code}/admin/"),
                (f"{code} operator full", op_full.username, "123456", f"/{code}/admin/"),
                (f"{code} operator limited", op_limited.username, "123456", f"/{code}/admin/"),
                (f"{code} tech 1", tech_user_1.username, "123456", f"/{code}/tech/"),
                (f"{code} tech 2", tech_user_2.username, "123456", f"/{code}/tech/"),
            ]

            if OperatorPermission:
                for key in OPERATOR_FULL_KEYS:
                    obj, created = OperatorPermission.objects.get_or_create(company=company, operator=op_full, permission_key=key, defaults={"is_allowed": True})
                    obj.is_allowed = True
                    obj.save(update_fields=["is_allowed"])
                    if created:
                        counts["operator_permissions"] += 1

                all_keys = sorted(set(OPERATOR_FULL_KEYS + OPERATOR_LIMITED_KEYS + ["outbox_list", "invoice_create", "communication_settings"]))
                for key in all_keys:
                    allow = key in OPERATOR_LIMITED_KEYS
                    obj, created = OperatorPermission.objects.get_or_create(company=company, operator=op_limited, permission_key=key, defaults={"is_allowed": allow})
                    obj.is_allowed = allow
                    obj.save(update_fields=["is_allowed"])
                    if created:
                        counts["operator_permissions"] += 1

            tech1 = self.create_technician(Technician, company, tech_user_1, f"{ci}111111111")
            tech2 = self.create_technician(Technician, company, tech_user_2, f"{ci}222222222")
            technicians = [tech1, tech2]
            counts["technicians"] += 2

            categories = []
            subcategories_by_category = {}
            item_defs_by_category = {}

            for cat_index, cat_title in enumerate(CATEGORY_NAMES, start=1):
                category = self.create_category(CompanyServiceCategory, company, cat_title, cat_index)
                categories.append(category)
                subcategories_by_category[category.id] = []
                item_defs_by_category[category.id] = []
                counts["service_categories"] += 1

                if CompanyService:
                    service = CompanyService()
                    set_fields(service, company=company, title=cat_title, description=f"سرویس تستی {cat_title}", base_price=Decimal(str(600000 + cat_index * 100000)), is_active=True)
                    save(service)

                for sub_index in range(1, 3):
                    sub = self.create_subcategory(CompanyServiceSubCategory, company, category, cat_title, sub_index)
                    subcategories_by_category[category.id].append(sub)
                    counts["service_subcategories"] += 1

                for item_index, kind in enumerate(["number", "money"], start=1):
                    if OrderItemDefinition:
                        item_def = OrderItemDefinition()
                        kind_value = pick_choice(OrderItemDefinition, "kind", [kind, "number", "money", "text"], kind)
                        set_fields(
                            item_def,
                            company=company,
                            category=category,
                            title=f"{cat_title} - فیلد سفارشی {item_index}",
                            kind=kind_value,
                            is_active=True,
                            sort_order=item_index,
                        )
                        save(item_def)
                        item_defs_by_category[category.id].append(item_def)
                        counts["order_item_definitions"] += 1

            if TechnicianCategorySkill:
                for tech_index, tech in enumerate(technicians, start=1):
                    for cat_index, category in enumerate(categories, start=1):
                        skill, created = TechnicianCategorySkill.objects.get_or_create(
                            technician=tech,
                            category=category,
                            defaults={"priority": 1 if tech_index == 1 else min(cat_index, 3)},
                        )
                        skill.priority = 1 if tech_index == 1 else min(cat_index, 3)
                        skill.save(update_fields=["priority"])
                        if created:
                            counts["technician_skills"] += 1

            if TechnicianSkill:
                for tech in technicians:
                    for category in categories[:2]:
                        skill, created = TechnicianSkill.objects.get_or_create(
                            company=company,
                            technician=tech,
                            name=category.title,
                            defaults={"level": "expert"},
                        )
                        if created:
                            counts["technician_skills"] += 1

            customers = []
            for customer_index in range(1, 6):
                customer = self.create_customer(Customer, company, customer_index, ci)
                customers.append(customer)
                counts["customers"] += 1

            if SMSProvider:
                provider_type = pick_choice(SMSProvider, "provider_type", ["fake", "FAKE"], "fake")
                provider, _ = SMSProvider.objects.get_or_create(company=company, provider_type=provider_type, defaults={"name": f"{company_name} Fake Provider", "api_key": "test", "sender_number": "1000", "is_active": True})
                set_fields(provider, name=f"{company_name} Fake Provider", api_key="test", sender_number="1000", is_active=True)
                save(provider)

            if CompanySMSWallet:
                wallet, _ = CompanySMSWallet.objects.get_or_create(company=company)
                set_fields(wallet, balance_rial=1500000 + ci * 250000)
                save(wallet)
                counts["wallets"] += 1

                if CompanySMSTransaction:
                    tx = CompanySMSTransaction()
                    set_fields(
                        tx,
                        company=company,
                        wallet=wallet,
                        transaction_type=pick_choice(CompanySMSTransaction, "transaction_type", ["CREDIT", "credit"], "CREDIT"),
                        amount_rial=1500000 + ci * 250000,
                        sms_parts=0,
                        message_length=0,
                        balance_after=1500000 + ci * 250000,
                        description="شارژ اولیه تستی seed",
                        created_by=admin,
                    )
                    save(tx)
                    counts["wallet_transactions"] += 1

            if NotificationSetting:
                for event_key in EVENT_KEYS:
                    setting, created = NotificationSetting.objects.get_or_create(company=company, event_key=event_key)
                    set_fields(setting, title=self.event_title(event_key), in_app_enabled=True, sms_enabled=True)
                    save(setting)
                    if created:
                        counts["notification_settings"] += 1

            if SMSTemplate:
                for event_key in EVENT_KEYS:
                    template, created = SMSTemplate.objects.get_or_create(company=company, key=event_key, defaults={"title": self.event_title(event_key), "template_text": self.template_text(event_key), "is_active": True})
                    set_fields(template, title=self.event_title(event_key), template_text=self.template_text(event_key), is_active=True, send_start_time=time(8, 0), send_end_time=time(22, 0))
                    save(template)
                    if created:
                        counts["sms_templates"] += 1

            orders = []
            statuses = [
                ("new", None),
                ("waiting", technicians[0]),
                ("in_progress", technicians[0]),
                ("done", technicians[1]),
                ("cancel_request", technicians[1]),
                ("cancelled", technicians[0]),
                ("new", None),
            ]

            for order_index in range(1, options["orders_per_company"] + 1):
                status_hint, tech = statuses[(order_index - 1) % len(statuses)]
                category = categories[(order_index - 1) % len(categories)]
                subcategory = subcategories_by_category[category.id][(order_index - 1) % 2]
                customer = customers[(order_index - 1) % len(customers)]
                order = self.create_order(Order, company, customer, tech, category, subcategory, status_hint, order_index, admin)
                orders.append(order)
                counts["orders"] += 1

                if OrderItemValue:
                    for def_index, item_def in enumerate(item_defs_by_category.get(category.id, []), start=1):
                        value, created = OrderItemValue.objects.get_or_create(order=order, item=item_def)
                        item_kind = str(getattr(item_def, "kind", "text")).lower()
                        set_fields(
                            value,
                            value_number=Decimal(str(order_index + def_index)) if item_kind in ("number", "money") else None,
                            value_text=f"مقدار تستی {order_index}-{def_index}" if item_kind == "text" else "",
                            value_bool=True if item_kind == "bool" else None,
                        )
                        save(value)
                        if created:
                            counts["order_item_values"] += 1

                if OrderStatusLog:
                    log = OrderStatusLog()
                    set_fields(log, company=company, order=order, old_status="new", new_status=order.status, changed_by=admin, note="لاگ تستی seed")
                    save(log)
                    counts["order_logs"] += 1

            if Notification:
                for order in orders[:5]:
                    recipient = order.technician.user if getattr(order, "technician_id", None) else admin
                    notif = Notification()
                    set_fields(
                        notif,
                        company=company,
                        recipient=recipient,
                        notification_type=pick_choice(Notification, "notification_type", ["order_assigned", "order_created"], "order_created"),
                        title=f"اعلان تست سفارش #{order.id}",
                        message=f"این اعلان تستی برای سفارش {order.title} است.",
                        is_read=False,
                        related_order=order,
                    )
                    save(notif)
                    counts["notifications"] += 1

            invoices = []
            invoice_status_hints = ["draft", "issued", "paid", "issued", "paid", "cancelled", "issued", "paid", "draft"]
            for invoice_index in range(1, options["invoices_per_company"] + 1):
                order = orders[(invoice_index - 1) % len(orders)]
                status_hint = invoice_status_hints[(invoice_index - 1) % len(invoice_status_hints)]
                invoice = self.create_invoice(Invoice, company, order, admin, invoice_index, status_hint)
                invoices.append(invoice)
                counts["invoices"] += 1

                if InvoiceItem:
                    for line_index in range(1, 3):
                        item = InvoiceItem()
                        quantity = Decimal(str(line_index))
                        unit_price = Decimal(str(450000 + invoice_index * 50000 + line_index * 75000))
                        set_fields(
                            item,
                            company=company,
                            invoice=invoice,
                            description=f"خدمت فاکتور {invoice_index}-{line_index}",
                            quantity=quantity,
                            unit_price=unit_price,
                            discount_amount=Decimal("0"),
                            sort_order=line_index,
                        )
                        save(item)
                        counts["invoice_items"] += 1

                    try:
                        invoice.recalculate_totals()
                    except Exception:
                        pass

            if NotificationEvent:
                event_status = pick_choice(NotificationEvent, "status", ["dispatched", "queued", "processed"], "dispatched")
                for event_index, event_key in enumerate(EVENT_KEYS[:8], start=1):
                    target_order = orders[(event_index - 1) % len(orders)]
                    event = NotificationEvent()
                    set_fields(
                        event,
                        company=company,
                        event_key=event_key,
                        status=event_status,
                        result_message="رویداد تستی ساخته‌شده توسط seed",
                        target_model="Order",
                        target_id=target_order.id,
                        dedup_key=f"seed:{company.code}:{event_key}:{target_order.id}:{event_index}",
                        payload={"seed": True, "company": company.code},
                    )
                    save(event)
                    counts["notification_events"] += 1

            if SMSOutbox:
                sms_status_cycle = self.sms_status_cycle(SMSOutbox)
                for sms_index in range(1, 19):
                    status = sms_status_cycle[(sms_index - 1) % len(sms_status_cycle)]
                    event_key = EVENT_KEYS[(sms_index - 1) % len(EVENT_KEYS)]
                    sms = SMSOutbox()
                    set_fields(
                        sms,
                        company=company,
                        provider=SMSProvider.objects.filter(company=company, is_active=True).first() if SMSProvider else None,
                        template_key=event_key,
                        phone_number=f"0919{ci}{sms_index:06d}"[:11],
                        message=f"پیامک تست شرکت {company_name} - {self.event_title(event_key)} - وضعیت {status}",
                        status=status,
                        attempt_count=1 if status in ("sending", "sent", "delivered", "failed") else 0,
                        provider_message_id=f"C-{code}-{sms_index}" if status in ("sent", "delivered") else "",
                        error_message="خطای تستی ارسال پیامک" if status == "failed" else "",
                        queued_at=timezone.now() - timedelta(minutes=sms_index),
                        sending_at=timezone.now() - timedelta(minutes=sms_index - 1) if status == "sending" else None,
                        sent_at=timezone.now() - timedelta(minutes=sms_index - 1) if status in ("sent", "delivered") else None,
                        delivered_at=timezone.now() if status == "delivered" else None,
                        failed_at=timezone.now() if status == "failed" else None,
                        send_at=timezone.now(),
                        order_id=orders[(sms_index - 1) % len(orders)].id,
                        invoice_id=invoices[(sms_index - 1) % len(invoices)].id,
                    )
                    save(sms)
                    counts["company_sms_outbox"] += 1

            if PlatformBillingInvoice:
                for bi, status_hint in enumerate(["UNPAID", "PAID"], start=1):
                    inv = PlatformBillingInvoice()
                    set_fields(
                        inv,
                        company=company,
                        invoice_number=f"PB-{company.code.upper()}-{bi:03d}",
                        invoice_type=pick_choice(PlatformBillingInvoice, "invoice_type", ["SMS_RECHARGE", "SUBSCRIPTION"], "SMS_RECHARGE"),
                        amount_rial=500000 * bi,
                        status=pick_choice(PlatformBillingInvoice, "status", [status_hint], status_hint),
                        description="فاکتور پلتفرمی تستی",
                        created_by=platform_owner,
                        paid_by=platform_owner if status_hint == "PAID" else None,
                        paid_at=timezone.now() if status_hint == "PAID" else None,
                    )
                    save(inv)
                    counts["platform_billing_invoices"] += 1

            if PlatformSMSOutbox:
                platform_sms_status_cycle = self.sms_status_cycle(PlatformSMSOutbox)
                for pi, event_key in enumerate(PLATFORM_EVENT_KEYS, start=1):
                    status = platform_sms_status_cycle[(pi - 1) % len(platform_sms_status_cycle)]
                    psms = PlatformSMSOutbox()
                    set_fields(
                        psms,
                        recipient_company=company,
                        company=company,
                        phone_number=admin.phone,
                        template_key=event_key,
                        message=f"پیامک پلتفرمی تست برای {company_name}: {self.event_title(event_key)} - وضعیت {status}",
                        status=status,
                        attempt_count=1 if status in ("sending", "sent", "delivered", "failed") else 0,
                        provider_message_id=f"P-{code}-{pi}" if status in ("sent", "delivered") else "",
                        error_message="خطای تستی پلتفرم" if status == "failed" else "",
                        queued_at=timezone.now() - timedelta(minutes=pi),
                        sent_at=timezone.now() if status in ("sent", "delivered") else None,
                        delivered_at=timezone.now() if status == "delivered" else None,
                        failed_at=timezone.now() if status == "failed" else None,
                        send_at=timezone.now(),
                    )
                    save(psms)
                    counts["platform_sms_outbox"] += 1

        # Ensure master SMS templates exist
        try:
            from apps.sms.master_template_defaults import ensure_master_templates
            ensure_master_templates()
        except Exception:
            pass

        return {
            "counts": counts,
            "credentials": credentials,
            "companies": selected_companies,
        }

    def create_company(self, Company, code, name, index):
        company = Company.objects.filter(code=code).first() or Company()
        set_fields(
            company,
            name=name,
            code=code,
            slug=code,
            is_active=True,
            email=f"info-{code}@demo.local",
            phone=f"021{index}000000",
            address=f"تهران، آدرس تست {name}",
            economic_code=f"ECON-{index:05d}",
            website=f"https://{code}.example.com",
        )
        return save(company)

    def create_category(self, Category, company, title, index):
        category = Category.objects.filter(company=company, title=title).first() or Category(company=company, title=title)
        set_fields(
            category,
            description=f"رسته تستی {title}",
            is_active=True,
            sort_order=index,
        )
        return save(category)

    def create_subcategory(self, SubCategory, company, category, cat_title, sub_index):
        title = f"{cat_title} - آیتم خدماتی {sub_index}"
        sub = SubCategory.objects.filter(company=company, category=category, title=title).first() or SubCategory(company=company, category=category, title=title)
        set_fields(
            sub,
            description=f"آیتم خدماتی تستی برای {cat_title}",
            base_price=Decimal(str(700000 + sub_index * 250000)),
            is_active=True,
            sort_order=sub_index,
        )
        return save(sub)

    def create_technician(self, Technician, company, user, national_id):
        tech = Technician.objects.filter(company=company, user=user).first() or Technician(company=company, user=user)
        set_fields(
            tech,
            national_id=national_id,
            is_available=True,
            rating=Decimal("4.8"),
            notes="تکنسین تستی seed",
            service_wage_percent=Decimal("60"),
            goods_wage_percent=Decimal("10"),
            travel_wage_percent=Decimal("100"),
        )
        return save(tech)

    def create_customer(self, Customer, company, customer_index, company_index):
        phone = f"0935{company_index}{customer_index:02d}{customer_index:04d}"[:11]
        customer = Customer.objects.filter(company=company, phone=phone).first() or Customer(company=company, phone=phone)
        set_fields(
            customer,
            first_name=f"مشتری",
            last_name=f"{customer_index} {company.name}",
            email=f"customer{company_index}{customer_index}@demo.local",
            address=f"تهران، خیابان تست {customer_index}، پلاک {customer_index}",
            notes="مشتری تستی seed",
        )
        return save(customer)

    def create_order(self, Order, company, customer, technician, category, subcategory, status_hint, index, admin):
        order = Order()
        status = pick_choice(Order, "status", [status_hint, "new"], "new")
        priority = pick_choice(Order, "priority", ["normal", "high", "urgent"], "normal")
        price = Decimal(str(900000 + index * 175000))
        set_fields(
            order,
            company=company,
            customer=customer,
            customer_name=full_name(customer.user) if getattr(customer, "user_id", None) else f"{customer.first_name} {customer.last_name}",
            customer_phone=customer.phone,
            technician=technician,
            title=f"سفارش تست {index} - {subcategory.title}",
            description=f"شرح تست برای {subcategory.title}",
            address=customer.address,
            service_date=timezone.localdate() + timedelta(days=index),
            scheduled_for=timezone.now() + timedelta(days=index),
            status=status,
            priority=priority,
            price_estimate=price,
            final_price=price if status in ("done", "completed") else Decimal("0"),
            extra_payment=Decimal("0"),
            wage_deduction=Decimal("0"),
            required_skill=category.title,
            service_category=category,
            service_subcategory=subcategory,
            accepted_at=timezone.now() - timedelta(hours=2) if technician else None,
            completed_at=timezone.now() if status in ("done", "completed") else None,
            notes="یادداشت تستی سفارش",
            internal_note="یادداشت داخلی تستی",
        )
        return save(order)

    def create_invoice(self, Invoice, company, order, admin, index, status_hint):
        invoice = Invoice()
        status = pick_choice(Invoice, "status", [status_hint, "issued"], "issued")
        number = f"INV-{company.code.upper()}-{index:05d}"
        tech_user = order.technician.user if getattr(order, "technician_id", None) else None
        set_fields(
            invoice,
            company=company,
            order=order,
            customer=order.customer,
            created_by=admin,
            invoice_number=number,
            public_code=f"{company.code}{index}{uuid.uuid4().hex[:10]}",
            status=status,
            customer_name_snapshot=order.display_customer_name,
            customer_phone_snapshot=order.display_customer_phone,
            address_snapshot=order.address,
            technician_name_snapshot=full_name(tech_user),
            technician_phone_snapshot=getattr(tech_user, "phone", ""),
            service_title_snapshot=order.title,
            service_date_snapshot=order.service_date,
            subtotal=Decimal("0"),
            tax_amount=Decimal("0"),
            discount_amount=Decimal("0"),
            total_amount=Decimal("0"),
            issued_at=timezone.now() if status in ("issued", "paid") else None,
            due_at=timezone.now() + timedelta(days=3),
            paid_at=timezone.now() if status == "paid" else None,
            notes="فاکتور تستی seed",
            footer_text="مسئولیت فاکتور صادره بر عهده ارائه‌دهنده خدمت می‌باشد.",
        )
        return save(invoice)

    def sms_status_cycle(self, Model):
        choices = set(get_choices(Model, "status"))
        if {"queued", "sending", "sent", "delivered", "failed", "cancelled"}.issubset(choices):
            return ["queued", "sending", "sent", "delivered", "failed", "cancelled"]
        if {"pending", "sent", "failed", "cancelled"}.issubset(choices):
            return ["pending", "sent", "failed", "cancelled"]
        if choices:
            return list(choices)
        return ["queued", "sent", "failed"]

    def event_title(self, event_key):
        labels = {
            "order_created_admin": "سفارش جدید",
            "order_available_technician": "سفارش جدید برای تکنسین",
            "order_assigned_technician": "تخصیص سفارش",
            "order_accepted_customer": "پذیرش سفارش",
            "order_completed_customer": "اتمام سفارش",
            "order_cancel_requested_admin": "درخواست لغو",
            "order_cancel_approved_technician": "تایید لغو",
            "order_cancel_rejected_technician": "رد لغو",
            "invoice_issued_customer": "صدور فاکتور",
            "payment_success_customer": "پرداخت موفق",
            "payment_failed_customer": "پرداخت ناموفق",
            "survey_request_customer": "نظرسنجی",
            "sms_credit_low_admin": "اعتبار پیامک کم",
            "sms_credit_empty_admin": "اعتبار پیامک تمام",
            "subscription_expiring_admin": "اشتراک در حال اتمام",
            "subscription_expired_admin": "اشتراک تمام شده",
            "platform_payment_success_admin": "پرداخت پلتفرمی موفق",
        }
        return labels.get(event_key, event_key)

    def template_text(self, event_key):
        return f"{self.event_title(event_key)} برای {{company_name}} - کد: {{order_id}}{{invoice_number}}"

    def print_summary(self, result):
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("DEMO SEED COMPLETED"))
        self.stdout.write("=" * 70)
        for key, value in result["counts"].items():
            self.stdout.write(f"{key}: {value}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Demo credentials"))
        self.stdout.write("-" * 70)
        for label, username, password, url in result["credentials"]:
            self.stdout.write(f"{label:24} | {username:28} | {password:8} | {url}")

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Useful URLs"))
        self.stdout.write("-" * 70)
        for code, _name in result["companies"]:
            self.stdout.write(f"http://127.0.0.1:8000/{code}/admin/")
            self.stdout.write(f"http://127.0.0.1:8000/{code}/admin/communication-settings/")
            self.stdout.write(f"http://127.0.0.1:8000/{code}/admin/sms/outbox/")
            self.stdout.write(f"http://127.0.0.1:8000/{code}/tech/")
        self.stdout.write("http://127.0.0.1:8000/owner-platform/platform-sms/outbox/")
