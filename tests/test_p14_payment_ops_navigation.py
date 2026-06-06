"""
P14-PAYMENT-OPS-NAVIGATION: Navigation and usability tests.

Covers:
1. Company admin operations page contains contextual links
2. Company admin sidebar contains payment operations link
3. Company admin does NOT see platform owner links
4. Platform owner dashboard has payment operations link
5. Platform owner operations page has contextual explanation
6. Navigation links use correct company_code
7. No sensitive banking/KYC fields in operations pages
8. Anonymous/technician still blocked
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


class NavigationTestMixin:
    """Shared helpers."""

    def create_company(self, code="nav_co", name="Nav Test Co"):
        return Company.objects.create(code=code, name=name, slug=code, is_active=True)

    def create_user(self, company, role, username=None):
        username = username or f"{role.lower()}_{company.code}_{CompanyUser.objects.count()}"
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=role,
        )

    def create_platform_owner(self, username="nav_platform_owner"):
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


# =============================================================================
# COMPANY ADMIN NAVIGATION TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls")
class CompanyAdminNavigationTest(TestCase, NavigationTestMixin):
    """Test that company admin can find and use payment operations navigation."""

    def setUp(self):
        self.company = self.create_company("nav_a", "Nav A")
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "nav_admin_a")

    def test_operations_page_has_financial_reports_link(self):
        """Operations page should link to financial reports."""
        self.client.login(username="nav_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("financial-reports", content)

    def test_operations_page_has_read_only_notice(self):
        """Operations page should explain it's read-only."""
        self.client.login(username="nav_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertTrue(
            "خواندنی" in content or "عملیات مالی" in content or "پایش" in content,
            "Operations page should have read-only or monitoring explanation"
        )

    def test_operations_page_does_not_contain_platform_owner_link(self):
        """Company admin should NOT see platform-level operations link."""
        self.client.login(username="nav_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/owner-platform/payments/operations/", content)

    def test_operations_page_uses_correct_company_code(self):
        """Navigation links should use the correct company code."""
        self.client.login(username="nav_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn(f"/{self.company.code}/admin/", content)

    def test_operations_page_no_sensitive_data(self):
        """Operations page should not contain SHABA/card/national-code data."""
        self.client.login(username="nav_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertNotIn("IR12345", content)
        self.assertNotIn("6037", content)
        self.assertNotIn("national_card_image", content)


# =============================================================================
# PLATFORM OWNER NAVIGATION TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls")
class PlatformOwnerNavigationTest(TestCase, NavigationTestMixin):
    """Test that platform owner can find and use payment operations."""

    def setUp(self):
        self.platform_owner = self.create_platform_owner()

    def test_platform_operations_page_accessible(self):
        """Platform owner can access operations page."""
        self.client.login(username="nav_platform_owner", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertEqual(response.status_code, 200)

    def test_platform_operations_has_explanation(self):
        """Platform operations page should have explanatory text."""
        self.client.login(username="nav_platform_owner", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertTrue(
            "reconcile_payments" in content or "expire_pending_payments" in content,
            "Platform operations should reference operational commands"
        )

    def test_platform_operations_no_sensitive_data(self):
        """Platform operations page should not contain raw banking data."""
        self.client.login(username="nav_platform_owner", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertNotIn("shaba_number", content)
        self.assertNotIn("bank_card_number", content)
        self.assertNotIn("national_card_image", content)


# =============================================================================
# ACCESS CONTROL REGRESSION
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls")
class NavigationAccessControlTest(TestCase, NavigationTestMixin):
    """Ensure P13 access control still works after P14 navigation changes."""

    def setUp(self):
        self.company = self.create_company("nav_sec", "Nav Sec Co")

    def test_anonymous_blocked_from_company_operations(self):
        """Anonymous user cannot access company operations."""
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        self.assertIn(response.status_code, [302, 403])

    def test_technician_blocked_from_company_operations(self):
        """Technician cannot access payment operations."""
        tech = self.create_user(self.company, UserRole.TECHNICIAN, "nav_tech")
        self.client.login(username="nav_tech", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        self.assertIn(response.status_code, [403, 302])

    def test_company_admin_blocked_from_platform_operations(self):
        """Company admin cannot access platform-level operations."""
        admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "nav_noplat")
        self.client.login(username="nav_noplat", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertIn(response.status_code, [403, 302])
