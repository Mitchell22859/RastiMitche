"""
P19-UI-CORE-LOW-RISK-POLISH-PACK: Smoke tests for polished pages.

Covers:
1. Company dashboard renders 200
2. Company dashboard has payment operations quick link
3. Platform owner dashboard renders 200
4. Platform owner dashboard has payment operations link
5. Payment operations pages render 200
6. No sensitive banking/KYC raw terms appear
7. No forbidden cross-tenant links
"""
from django.test import TestCase, override_settings

from apps.accounts.models import CompanyUser, UserRole
from apps.tenants.models import Company


class P19TestMixin:
    def create_company(self, code="p19_co"):
        return Company.objects.create(code=code, name="P19 Co", slug=code, is_active=True)

    def create_user(self, company, role, username):
        return CompanyUser.objects.create_user(
            username=username, password="testpass123", company=company, role=role,
        )

    def create_platform_owner(self):
        return CompanyUser.objects.create_user(
            username="p19_platform", password="testpass123",
            company=None, role=UserRole.PLATFORM_OWNER,
        )


@override_settings(ROOT_URLCONF="config.urls")
class CompanyDashboardSmokeTest(TestCase, P19TestMixin):
    """Company admin dashboard renders and contains expected links."""

    def setUp(self):
        self.company = self.create_company()
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "p19_admin")

    def test_dashboard_renders_200(self):
        self.client.login(username="p19_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        self.assertEqual(response.status_code, 200)

    def test_dashboard_has_payment_operations_link(self):
        self.client.login(username="p19_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode("utf-8")
        self.assertIn("/admin/payments/operations/", content)
        self.assertIn("عملیات پرداخت", content)

    def test_dashboard_no_platform_link(self):
        self.client.login(username="p19_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/owner-platform/payments/operations/", content)

    def test_dashboard_no_sensitive_data(self):
        self.client.login(username="p19_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/")
        content = response.content.decode("utf-8")
        self.assertNotIn("shaba_number", content)
        self.assertNotIn("national_card_image", content)


@override_settings(ROOT_URLCONF="config.urls")
class PlatformDashboardSmokeTest(TestCase, P19TestMixin):
    """Platform owner dashboard renders and has expected links."""

    def setUp(self):
        self.owner = self.create_platform_owner()

    def test_platform_dashboard_renders_200(self):
        self.client.login(username="p19_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        self.assertEqual(response.status_code, 200)

    def test_platform_dashboard_has_operations_link(self):
        self.client.login(username="p19_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        content = response.content.decode("utf-8")
        self.assertIn("/owner-platform/payments/operations/", content)
        self.assertIn("پایش پرداخت‌ها", content)

    def test_platform_no_tenant_link(self):
        self.client.login(username="p19_platform", password="testpass123")
        response = self.client.get("/owner-platform/dashboard/")
        content = response.content.decode("utf-8")
        self.assertNotIn("/admin/payments/operations/", content)


@override_settings(ROOT_URLCONF="config.urls")
class PaymentOperationsRenderTest(TestCase, P19TestMixin):
    """Payment operations pages render correctly after CSS changes."""

    def setUp(self):
        self.company = self.create_company("p19_ops")
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "p19_ops_admin")
        self.owner = self.create_platform_owner()

    def test_company_operations_renders(self):
        self.client.login(username="p19_ops_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("سالم", content)  # Healthy state

    def test_platform_operations_renders(self):
        self.client.login(username="p19_platform", password="testpass123")
        response = self.client.get("/owner-platform/payments/operations/")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode("utf-8")
        self.assertIn("سالم", content)

    def test_company_operations_uses_shared_classes(self):
        """Empty state should use shared CSS classes, not only inline styles."""
        self.client.login(username="p19_ops_admin", password="testpass123")
        response = self.client.get(f"/{self.company.code}/admin/payments/operations/")
        content = response.content.decode("utf-8")
        self.assertIn("empty-state-healthy", content)
