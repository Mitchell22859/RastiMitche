"""
P13-PAYMENT-OPERATIONS-DASHBOARD: Tests for payment operations views.

Covers:
1. Company admin can access own payment operations page
2. Company admin cannot access another company's operations page
3. Platform owner can access platform operations page
4. Non-platform owner cannot access platform operations page
5. Company staff behavior (OperatorPermissionMiddleware may block)
6. Technician/customer cannot access
7. Dashboard shows only own company payments
8. Pending/failed counts are correct
9. Old pending count respects PAYMENT_EXPIRATION_MINUTES
10. Cash/manual payments do not pollute gateway-problem counts
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


class OperationsTestMixin:
    """Shared helpers."""

    def create_company(self, code="ops_co", name="Ops Test Co"):
        return Company.objects.create(code=code, name=name, slug=code, is_active=True)

    def create_user(self, company, role, username=None):
        username = username or f"{role.lower()}_{company.code}_{CompanyUser.objects.count()}"
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=role,
        )

    def create_platform_owner(self, username="ops_platform_owner"):
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
# PERMISSION TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls")
class CompanyOperationsPermissionTest(TestCase, OperationsTestMixin):
    """Test access control for company payment operations page."""

    def setUp(self):
        self.company_a = self.create_company("ops_a", "Ops A")
        self.company_b = self.create_company("ops_b", "Ops B")
        self.admin_a = self.create_user(self.company_a, UserRole.COMPANY_ADMIN, "ops_admin_a")
        self.admin_b = self.create_user(self.company_b, UserRole.COMPANY_ADMIN, "ops_admin_b")

    def test_admin_can_access_own_operations(self):
        """Company admin can access own payment operations page."""
        self.client.login(username="ops_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company_a.code}/admin/payments/operations/")
        self.assertEqual(response.status_code, 200)

    def test_admin_cannot_access_other_company_operations(self):
        """Company A admin cannot access Company B's operations."""
        self.client.login(username="ops_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company_b.code}/admin/payments/operations/")
        self.assertIn(response.status_code, [403, 302])

    def test_technician_cannot_access(self):
        """Technician cannot access payment operations."""
        tech = self.create_user(self.company_a, UserRole.TECHNICIAN, "ops_tech")
        self.client.login(username="ops_tech", password="testpass123")
        response = self.client.get(f"/{self.company_a.code}/admin/payments/operations/")
        self.assertIn(response.status_code, [403, 302])

    def test_anonymous_cannot_access(self):
        """Anonymous user cannot access."""
        response = self.client.get(f"/{self.company_a.code}/admin/payments/operations/")
        self.assertIn(response.status_code, [302, 403])


@override_settings(ROOT_URLCONF="config.urls")
class PlatformOperationsPermissionTest(TestCase, OperationsTestMixin):
    """Test access control for platform payment operations page."""

    def setUp(self):
        self.company = self.create_company("ops_plat", "Ops Platform")
        self.platform_owner = self.create_platform_owner()

    def test_platform_owner_can_access(self):
        """Platform owner can access platform operations page."""
        self.client.login(username="ops_platform_owner", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertEqual(response.status_code, 200)

    def test_company_admin_cannot_access_platform_operations(self):
        """Company admin cannot access platform-level operations."""
        admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "ops_noplat")
        self.client.login(username="ops_noplat", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertIn(response.status_code, [403, 302])


# =============================================================================
# DATA CORRECTNESS TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls", PAYMENT_EXPIRATION_MINUTES=30)
class CompanyOperationsDataTest(TestCase, OperationsTestMixin):
    """Test that operations dashboard shows correct data for the company."""

    def setUp(self):
        self.company = self.create_company("data_co", "Data Co")
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "data_admin")
        self.gw = self.create_gateway(self.company)

    def test_shows_only_own_company_payments(self):
        """Dashboard shows only own company's gateway payments."""
        other = self.create_company("other_co", "Other")
        other_gw = self.create_gateway(other)
        inv_own = self.create_invoice(self.company)
        inv_other = self.create_invoice(other)
        self.create_gateway_payment(self.company, inv_own, self.gw, "pending", age_minutes=60)
        self.create_gateway_payment(other, inv_other, other_gw, "pending", age_minutes=60)

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["old_pending_count"], 1)  # Only own

    def test_old_pending_count_respects_threshold(self):
        """Only payments older than PAYMENT_EXPIRATION_MINUTES are counted."""
        inv = self.create_invoice(self.company)
        # Old (60 min) → counted
        self.create_gateway_payment(self.company, inv, self.gw, "pending", age_minutes=60)
        # Fresh (5 min) → not counted
        inv2 = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv2, self.gw, "pending", age_minutes=5)

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["old_pending_count"], 1)

    def test_cash_payments_not_in_gateway_counts(self):
        """Cash/manual payments (no gateway) do not appear in gateway problem counts."""
        inv = self.create_invoice(self.company)
        Payment.objects.create(
            company=self.company, invoice=inv, gateway=None,
            amount=inv.total_amount, status=Payment.Status.PENDING,
            metadata={"method": "cash"},
        )
        # Backdate
        Payment.objects.filter(company=self.company).update(
            created_at=timezone.now() - timedelta(minutes=60)
        )

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["old_pending_count"], 0)

    def test_paid_payment_not_problematic(self):
        """PAID payments should not appear as problematic."""
        inv = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv, self.gw, "paid", age_minutes=60)

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["old_pending_count"], 0)
        self.assertEqual(len(health["problematic_payments"]), 0)

    def test_failed_recent_count(self):
        """Failed gateway payments within 7 days are counted."""
        inv = self.create_invoice(self.company)
        self.create_gateway_payment(self.company, inv, self.gw, "failed", age_minutes=60)

        from apps.payments.selectors_operations import PaymentOperationsSelector
        health = PaymentOperationsSelector.get_company_payment_health(self.company)
        self.assertEqual(health["failed_recent_count"], 1)
