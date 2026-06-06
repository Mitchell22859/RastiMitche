"""
P16-PAYMENT-OPS-QUICK-LINKS-AND-EMPTY-STATES-POLISH: Tests.

Covers:
1. Company admin dashboard contains payment operations quick link
2. Company dashboard quick link uses correct company_code
3. Company dashboard does NOT contain platform owner payment link
4. Platform owner dashboard contains platform payment operations link
5. Platform owner dashboard does NOT contain tenant payment link
6. Company operations healthy empty state text appears
7. Platform operations healthy empty state text appears
8. Operations pages contain read-only notice
9. No sensitive data in dashboard/operations pages
10. P13/P14/P15 tests remain compatible
"""
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class QuickLinkTestMixin:
    """Shared helpers."""

    def create_company(self, code="ql_co", name="Quick Link Co"):
        return Company.objects.create(code=code, name=name, slug=code, is_active=True)

    def create_user(self, company, role, username=None):
        username = username or f"{role.lower()}_{company.code}_{CompanyUser.objects.count()}"
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=company, role=role,
        )

    def create_platform_owner(self, username="ql_platform_owner"):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


# =============================================================================
# COMPANY ADMIN DASHBOARD QUICK LINKS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls")
class CompanyDashboardQuickLinkTest(TestCase, QuickLinkTestMixin):
    """Test that company admin dashboard has payment operations quick link."""

    def setUp(self):
        self.company = self.create_company("ql_a", "QL Company A")
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "ql_admin_a")

    def test_dashboard_has_payment_operations_link(self):
        """Company admin dashboard should contain a link to payment operations."""
        self.client.login(username="ql_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("/admin/payments/operations/", content)
        self.assertIn("عملیات پرداخت", content)

    def test_dashboard_quick_link_uses_correct_company_code(self):
        """Quick link should use the correct company code in URL."""
        self.client.login(username="ql_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode("utf-8")
        self.assertIn(f"/{self.company.code}/admin/payments/operations/", content)

    def test_dashboard_does_not_show_platform_operations_link(self):
        """Company dashboard should NOT contain platform-level operations link."""
        self.client.login(username="ql_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/owner-platform/payments/operations/", content)

    def test_dashboard_no_sensitive_data(self):
        """Dashboard should not contain sensitive banking/KYC data."""
        self.client.login(username="ql_admin_a", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode("utf-8")
        self.assertNotIn("shaba_number", content)
        self.assertNotIn("national_card_image", content)


# =============================================================================
# PLATFORM OWNER DASHBOARD QUICK LINKS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls")
class PlatformDashboardQuickLinkTest(TestCase, QuickLinkTestMixin):
    """Test that platform owner dashboard has payment operations quick link."""

    def setUp(self):
        self.platform_owner = self.create_platform_owner()

    def test_platform_dashboard_has_operations_link(self):
        """Platform dashboard should contain payment operations quick link."""
        self.client.login(username="ql_platform_owner", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("/owner-platform/payments/operations/", content)
        self.assertIn("پایش پرداخت‌ها", content)

    def test_platform_dashboard_no_tenant_operations_link(self):
        """Platform dashboard should NOT have tenant-specific operations link."""
        self.client.login(username="ql_platform_owner", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        content = response.content.decode("utf-8")
        # Should not contain company-specific payment operations URL pattern
        self.assertNotIn("/admin/payments/operations/", content)


# =============================================================================
# EMPTY STATE / HEALTHY STATE TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls")
class EmptyStateTest(TestCase, QuickLinkTestMixin):
    """Test that empty/healthy state messages are clear and helpful."""

    def setUp(self):
        self.company = self.create_company("es_co", "Empty State Co")
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "es_admin")
        self.platform_owner = self.create_platform_owner("es_platform")

    def test_company_operations_healthy_state(self):
        """Company operations page should show clear healthy message when no problems."""
        self.client.login(username="es_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn("همه چیز سالم است", content)
        self.assertIn("callback", content)

    def test_platform_operations_healthy_state(self):
        """Platform operations page should show clear healthy message when no problems."""
        self.client.login(username="es_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn("سالم هستند", content)

    def test_company_operations_has_read_only_notice(self):
        """Company operations should mention it's read-only/informational."""
        self.client.login(username="es_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        # Should reference cash control or read-only nature
        self.assertTrue(
            "خواندنی" in content or "کنترل نقدی" in content or "نقدی و دستی" in content,
            "Operations page should indicate it's read-only or reference cash control"
        )

    def test_platform_operations_references_commands(self):
        """Platform operations should reference operational commands."""
        self.client.login(username="es_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn("expire_pending_payments", content)
        self.assertIn("reconcile_payments", content)
