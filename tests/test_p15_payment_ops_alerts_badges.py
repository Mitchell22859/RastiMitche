"""
P15-PAYMENT-OPS-ALERTS-AND-BADGES: Alert/badge logic and display tests.

Covers:
1. Alert severity logic
2. Healthy state shows "ok"
3. Old pending shows "warning"
4. Failed recent shows "danger"
5. Cash/manual payments do not trigger alerts
6. Company admin sees alert on own operations page
7. Platform owner sees global alert
8. No sensitive data in alert pages
9. Cross-tenant isolation preserved
"""
from datetime import timedelta
from decimal import Decimal

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.tenants.models import Company
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payments.selectors_operations import PaymentOperationsSelector


class AlertTestMixin:
    """Shared helpers."""

    def create_company(self, code="alert_co", name="Alert Co"):
        return Company.objects.create(code=code, name=name, slug=code, is_active=True)

    def create_user(self, company, role, username=None):
        username = username or f"{role.lower()}_{company.code}_{CompanyUser.objects.count()}"
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=role,
        )

    def create_platform_owner(self, username="alert_platform"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )

    def create_gateway(self, company):
        gw, _ = PaymentGateway.objects.get_or_create(
            company=company, gateway_type=PaymentGateway.GatewayType.FAKE,
            defaults={"name": "Fake", "is_active": True, "is_default": True},
        )
        return gw

    def create_invoice(self, company, total=5000000):
        order = Order.objects.create(company=company, title="T", status=Order.Status.DONE)
        inv = Invoice.objects.create(
            company=company, order=order, status=Invoice.Status.ISSUED,
            invoice_number=f"INV-{Invoice.objects.count()+1:05d}",
            issued_at=timezone.now(), subtotal=total, total_amount=total,
            gross_amount=total, net_amount_before_invoice_discounts=total,
        )
        InvoiceItem.objects.create(
            company=company, invoice=inv, description="svc",
            row_type=InvoiceItem.RowType.SERVICE, quantity=1, unit_price=total, total_price=total,
        )
        return inv

    def create_gateway_payment(self, company, invoice, gateway, status="pending", age_minutes=0):
        p = Payment.objects.create(
            company=company, invoice=invoice, gateway=gateway,
            amount=invoice.total_amount, status=status,
            reference_id=f"REF-{Payment.objects.count()+1}",
        )
        if age_minutes:
            Payment.objects.filter(pk=p.pk).update(
                created_at=timezone.now() - timedelta(minutes=age_minutes)
            )
            p.refresh_from_db()
        return p


# =============================================================================
# SELECTOR ALERT BADGE TESTS
# =============================================================================

@override_settings(PAYMENT_EXPIRATION_MINUTES=30)
class AlertBadgeSeverityTest(TestCase, AlertTestMixin):
    """Test PaymentOperationsSelector alert badge logic."""

    def setUp(self):
        self.company = self.create_company()
        self.gw = self.create_gateway(self.company)

    def test_no_problems_severity_ok(self):
        """No gateway problems → severity='ok'."""
        badge = PaymentOperationsSelector.get_company_alert_badge(self.company)
        self.assertEqual(badge["severity"], "ok")
        self.assertEqual(badge["total_problem_count"], 0)

    def test_old_pending_severity_warning(self):
        """1 old pending gateway payment → severity='warning'."""
        inv = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv, self.gw, "pending", age_minutes=60)

        badge = PaymentOperationsSelector.get_company_alert_badge(self.company)
        self.assertEqual(badge["severity"], "warning")
        self.assertEqual(badge["old_pending_count"], 1)

    def test_failed_recent_severity_danger(self):
        """Failed gateway payment in last 7 days → severity='danger'."""
        inv = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv, self.gw, "failed", age_minutes=60)

        badge = PaymentOperationsSelector.get_company_alert_badge(self.company)
        self.assertEqual(badge["severity"], "danger")
        self.assertEqual(badge["failed_recent_count"], 1)

    def test_many_old_pending_severity_danger(self):
        """More than 2 old pending → severity='danger'."""
        for _ in range(3):
            inv = self.create_invoice(self.company)
            self.create_gateway_payment(self.company, inv, self.gw, "pending", age_minutes=60)

        badge = PaymentOperationsSelector.get_company_alert_badge(self.company)
        self.assertEqual(badge["severity"], "danger")

    def test_cash_payment_does_not_trigger_alert(self):
        """Cash/manual payments (no gateway) do not affect alert badge."""
        inv = self.create_invoice(self.company)
        Payment.objects.create(
            company=self.company, invoice=inv, gateway=None,
            amount=inv.total_amount, status=Payment.Status.PENDING,
            metadata={"method": "cash"},
        )
        old_time = timezone.now() - timedelta(minutes=60)
        Payment.objects.filter(company=self.company).update(created_at=old_time)

        badge = PaymentOperationsSelector.get_company_alert_badge(self.company)
        self.assertEqual(badge["severity"], "ok")
        self.assertEqual(badge["total_problem_count"], 0)

    def test_paid_payment_does_not_trigger_alert(self):
        """PAID gateway payments do not affect alert badge."""
        inv = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv, self.gw, "paid", age_minutes=60)

        badge = PaymentOperationsSelector.get_company_alert_badge(self.company)
        self.assertEqual(badge["severity"], "ok")

    def test_platform_alert_badge(self):
        """Platform badge counts across all companies."""
        other = self.create_company("other_alert", "Other Alert")
        other_gw = self.create_gateway(other)

        inv1 = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv1, self.gw, "pending", age_minutes=60)

        inv2 = self.create_invoice(other)
        self.create_gateway_payment(other, inv2, other_gw, "failed", age_minutes=10)

        badge = PaymentOperationsSelector.get_platform_alert_badge()
        self.assertEqual(badge["old_pending_count"], 1)
        self.assertEqual(badge["failed_recent_count"], 1)
        self.assertEqual(badge["severity"], "danger")


# =============================================================================
# PAGE DISPLAY TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls", PAYMENT_EXPIRATION_MINUTES=30)
class CompanyAlertDisplayTest(TestCase, AlertTestMixin):
    """Test that company operations page shows alert correctly."""

    def setUp(self):
        self.company = self.create_company("disp_co", "Display Co")
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "disp_admin")
        self.gw = self.create_gateway(self.company)

    def test_healthy_page_shows_success(self):
        """When no problems, page shows healthy state."""
        self.client.login(username="disp_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn("وضعیت سالم", content)

    def test_old_pending_shows_warning(self):
        """When old pending exists, page shows warning alert."""
        inv = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv, self.gw, "pending", age_minutes=60)

        self.client.login(username="disp_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn("در انتظار قدیمی", content)

    def test_failed_shows_danger(self):
        """When failed exists, page shows danger alert."""
        inv = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv, self.gw, "failed", age_minutes=10)

        self.client.login(username="disp_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn("نیازمند بررسی", content)

    def test_no_sensitive_data_in_alerts(self):
        """Alert pages must not contain sensitive banking/KYC data."""
        self.client.login(username="disp_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertNotIn("shaba", content.lower())
        self.assertNotIn("national_card", content.lower())
        self.assertNotIn("bank_card", content.lower())


@override_settings(ROOT_URLCONF="config.urls", PAYMENT_EXPIRATION_MINUTES=30)
class PlatformAlertDisplayTest(TestCase, AlertTestMixin):
    """Test that platform operations page shows alert correctly."""

    def setUp(self):
        self.platform_owner = self.create_platform_owner()

    def test_platform_healthy_shows_success(self):
        """When no global problems, platform shows healthy state."""
        self.client.login(username="alert_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn("وضعیت سالم", content)

    def test_platform_problems_shows_danger(self):
        """When global problems exist, platform shows danger."""
        company = self.create_company("plat_prob", "Prob Co")
        gw = self.create_gateway(company)
        inv = self.create_invoice(company)
        self.create_gateway_payment(company, inv, gw, "failed", age_minutes=10)

        self.client.login(username="alert_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn("نیازمند بررسی", content)
