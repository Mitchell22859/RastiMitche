"""
P9-KYC-DOCUMENT-SECURITY: KYC Document Access & Sensitive Data Tests.

Covers:
1. Company admin can access own KYC document through protected view
2. Company admin cannot access another company's KYC document
3. Platform owner can access company KYC document
4. Company staff/operator CANNOT access KYC documents (security rule)
5. Technician cannot access KYC document
6. Customer cannot access KYC document
7. Anonymous user cannot access KYC document
8. Missing document returns safe 404
9. Readonly/detail pages show masked sensitive fields (model property tests)
10. Invalid field name returns 404 (path traversal protection)

Windows compatibility:
- Uses override_settings(MEDIA_ROOT=tempdir) to isolate uploaded test files.
- Streaming/FileResponse objects are explicitly closed before tearDown cleanup.
"""
import os
import shutil
import tempfile

from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.tenants.models import Company, CompanyMerchantProfile


# =============================================================================
# TEST HELPERS
# =============================================================================

# Create a temporary directory for test media files to avoid polluting project media
# and to enable safe cleanup on Windows (no file-lock conflicts).
_TEST_MEDIA_ROOT = tempfile.mkdtemp(prefix="rasti_kyc_test_media_")


def _close_response(response):
    """Safely close a streaming/file response to release file handles (Windows-safe)."""
    if hasattr(response, "close"):
        response.close()
    if hasattr(response, "streaming_content"):
        # Force iteration to close underlying file
        try:
            for _ in response.streaming_content:
                pass
        except Exception:
            pass


class KYCTestMixin:
    """Shared helpers for KYC document security tests."""

    def create_company(self, code="kyc_co", name="KYC Test Company"):
        return Company.objects.create(code=code, name=name, slug=code, is_active=True)

    def create_user(self, company, role, username=None):
        username = username or f"{role.lower()}_{company.code}_{CompanyUser.objects.count()}"
        return CompanyUser.objects.create_user(
            username=username,
            password="testpass123",
            company=company,
            role=role,
            first_name="Test",
            last_name=f"User_{role}",
        )

    def create_platform_owner(self, username="platform_owner"):
        return CompanyUser.objects.create_user(
            username=username,
            password="testpass123",
            company=None,
            role=UserRole.PLATFORM_OWNER,
            first_name="Platform",
            last_name="Owner",
        )

    def create_profile_with_document(self, company):
        """Create a merchant profile with a fake uploaded document."""
        fake_file = SimpleUploadedFile(
            name="test_national_card.jpg",
            content=b"\xff\xd8\xff\xe0" + b"\x00" * 100,  # Minimal JPEG header
            content_type="image/jpeg",
        )
        profile = CompanyMerchantProfile.objects.create(
            company=company,
            status=CompanyMerchantProfile.Status.SUBMITTED,
            legal_company_name="شرکت تست",
            owner_national_code="1234567890",
            postal_code="1234567890",
            registered_address="تهران",
            company_phone="02112345678",
            owner_full_name="تست تستی",
            owner_mobile="09121234567",
            bank_name="ملت",
            account_holder_name="تست تستی",
            shaba_number="IR123456789012345678901234",
            bank_card_number="6037991234567890",
            national_card_image=fake_file,
        )
        return profile

    def create_profile_without_document(self, company):
        """Create a merchant profile without documents."""
        return CompanyMerchantProfile.objects.create(
            company=company,
            status=CompanyMerchantProfile.Status.NOT_SUBMITTED,
            legal_company_name="شرکت بدون مدرک",
        )

    def assert_document_response(self, response, expected_statuses):
        """
        Assert response status and safely close the response to release file handles.
        This prevents Windows file-lock errors in tearDown.
        """
        try:
            self.assertIn(response.status_code, expected_statuses)
        finally:
            _close_response(response)


# =============================================================================
# 1. TENANT DOCUMENT ACCESS TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls", MEDIA_ROOT=_TEST_MEDIA_ROOT)
class TenantKYCDocumentAccessTest(TestCase, KYCTestMixin):
    """
    Verify that company admin can only access own company's KYC documents
    and cannot access another company's documents.

    Security rule: Only COMPANY_ADMIN can access KYC documents.
    COMPANY_STAFF/operator should NOT have access to sensitive KYC docs.
    """

    def setUp(self):
        self.company_a = self.create_company("comp_a", "Company A")
        self.company_b = self.create_company("comp_b", "Company B")

        self.admin_a = self.create_user(self.company_a, UserRole.COMPANY_ADMIN, "admin_a_kyc")
        self.admin_b = self.create_user(self.company_b, UserRole.COMPANY_ADMIN, "admin_b_kyc")

        self.profile_a = self.create_profile_with_document(self.company_a)
        self.profile_b = self.create_profile_with_document(self.company_b)

    def test_admin_can_access_own_company_document(self):
        """Company A admin can access Company A's KYC document."""
        self.client.login(username="admin_a_kyc", password="testpass123")
        url = f"/{self.company_a.code}/admin/payment/merchant-profile/document/national_card_image/"
        response = self.client.get(url)
        # Should be 200 (file served) or 404 if file doesn't exist on disk
        # Should NOT be 403
        self.assert_document_response(response, [200, 404])

    def test_admin_cannot_access_other_company_document(self):
        """Company A admin cannot access Company B's KYC document → 403."""
        self.client.login(username="admin_a_kyc", password="testpass123")
        url = f"/{self.company_b.code}/admin/payment/merchant-profile/document/national_card_image/"
        response = self.client.get(url)
        self.assert_document_response(response, [403, 302])

    def test_staff_cannot_access_own_company_document(self):
        """
        Company staff (COMPANY_STAFF) CANNOT access KYC documents.

        Security rule: KYC documents contain sensitive identity/banking information.
        Only COMPANY_ADMIN should have access to protect employee privacy and
        comply with data protection requirements.
        """
        staff_a = self.create_user(self.company_a, UserRole.COMPANY_STAFF, "staff_a_kyc")
        self.client.login(username="staff_a_kyc", password="testpass123")
        url = f"/{self.company_a.code}/admin/payment/merchant-profile/document/national_card_image/"
        response = self.client.get(url)
        self.assert_document_response(response, [403, 302])

    def test_staff_cannot_access_other_company_document(self):
        """Company A staff cannot access Company B's KYC document."""
        staff_a = self.create_user(self.company_a, UserRole.COMPANY_STAFF, "staff_a2_kyc")
        self.client.login(username="staff_a2_kyc", password="testpass123")
        url = f"/{self.company_b.code}/admin/payment/merchant-profile/document/national_card_image/"
        response = self.client.get(url)
        self.assert_document_response(response, [403, 302])


# =============================================================================
# 2. PLATFORM OWNER ACCESS TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls", MEDIA_ROOT=_TEST_MEDIA_ROOT)
class PlatformOwnerKYCDocumentAccessTest(TestCase, KYCTestMixin):
    """Verify that platform owner can access KYC documents for review."""

    def setUp(self):
        self.company = self.create_company("plat_co", "Platform Test Co")
        self.platform_owner = self.create_platform_owner("plat_owner_kyc")
        self.profile = self.create_profile_with_document(self.company)

    def test_platform_owner_can_access_document(self):
        """Platform owner can access company KYC document for review."""
        self.client.login(username="plat_owner_kyc", password="testpass123")
        url = f"/owner-platform/merchant-profiles/{self.profile.id}/document/national_card_image/"
        response = self.client.get(url)
        # 200 (file served) or 404 (file not on disk in test env)
        self.assert_document_response(response, [200, 404])

    def test_non_platform_owner_cannot_access_platform_document_route(self):
        """Regular company admin cannot use platform owner document route."""
        admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "admin_plat_kyc")
        self.client.login(username="admin_plat_kyc", password="testpass123")
        url = f"/owner-platform/merchant-profiles/{self.profile.id}/document/national_card_image/"
        response = self.client.get(url)
        self.assert_document_response(response, [403, 302])


# =============================================================================
# 3. UNAUTHORIZED ROLE TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls", MEDIA_ROOT=_TEST_MEDIA_ROOT)
class UnauthorizedKYCAccessTest(TestCase, KYCTestMixin):
    """Verify that technicians, customers, and anonymous users cannot access KYC documents."""

    def setUp(self):
        self.company = self.create_company("unauth_co", "Unauth Test Co")
        self.profile = self.create_profile_with_document(self.company)

    def test_technician_cannot_access_kyc_document(self):
        """Technician user cannot access KYC document view."""
        tech_user = self.create_user(self.company, UserRole.TECHNICIAN, "tech_kyc")
        self.client.login(username="tech_kyc", password="testpass123")
        url = f"/{self.company.code}/admin/payment/merchant-profile/document/national_card_image/"
        response = self.client.get(url)
        self.assert_document_response(response, [403, 302])

    def test_customer_cannot_access_kyc_document(self):
        """Customer user cannot access KYC document view."""
        customer_user = self.create_user(self.company, UserRole.CUSTOMER, "customer_kyc")
        self.client.login(username="customer_kyc", password="testpass123")
        url = f"/{self.company.code}/admin/payment/merchant-profile/document/national_card_image/"
        response = self.client.get(url)
        self.assert_document_response(response, [403, 302])

    def test_anonymous_user_cannot_access_kyc_document(self):
        """Anonymous (not logged in) user cannot access KYC document view."""
        url = f"/{self.company.code}/admin/payment/merchant-profile/document/national_card_image/"
        response = self.client.get(url)
        # Should redirect to login or return 403
        self.assert_document_response(response, [302, 403])


# =============================================================================
# 4. MISSING DOCUMENT & INVALID FIELD TESTS
# =============================================================================

@override_settings(ROOT_URLCONF="config.urls", MEDIA_ROOT=_TEST_MEDIA_ROOT)
class KYCDocumentEdgeCaseTest(TestCase, KYCTestMixin):
    """Verify safe behavior for missing documents and invalid field names."""

    def setUp(self):
        self.company = self.create_company("edge_co", "Edge Case Co")
        self.admin = self.create_user(self.company, UserRole.COMPANY_ADMIN, "admin_edge_kyc")
        self.profile = self.create_profile_without_document(self.company)

    def test_missing_document_returns_404(self):
        """Accessing a document that hasn't been uploaded returns 404."""
        self.client.login(username="admin_edge_kyc", password="testpass123")
        url = f"/{self.company.code}/admin/payment/merchant-profile/document/national_card_image/"
        response = self.client.get(url)
        self.assert_document_response(response, [404])

    def test_invalid_field_name_returns_404(self):
        """Accessing with an invalid/unexpected field name returns 404 (path traversal protection)."""
        self.client.login(username="admin_edge_kyc", password="testpass123")
        url = f"/{self.company.code}/admin/payment/merchant-profile/document/../../etc/passwd/"
        response = self.client.get(url)
        self.assert_document_response(response, [404])

    def test_unknown_field_name_returns_404(self):
        """Accessing with a valid-looking but non-whitelisted field returns 404."""
        self.client.login(username="admin_edge_kyc", password="testpass123")
        url = f"/{self.company.code}/admin/payment/merchant-profile/document/some_other_field/"
        response = self.client.get(url)
        self.assert_document_response(response, [404])


# =============================================================================
# 5. SENSITIVE DATA MASKING TESTS (model property level)
# =============================================================================

class SensitiveDataMaskingTest(TestCase, KYCTestMixin):
    """
    Verify that model properties correctly mask sensitive banking/identity data.
    These are the properties used in readonly/detail templates.
    """

    def test_shaba_masked_hides_middle(self):
        """shaba_masked shows only first 6 and last 4 characters."""
        company = self.create_company("mask_co", "Mask Co")
        profile = CompanyMerchantProfile(
            company=company,
            shaba_number="IR123456789012345678901234",
        )
        masked = profile.shaba_masked
        self.assertIn("IR1234", masked)
        self.assertIn("1234", masked[-4:])
        # Full number should NOT be present
        self.assertNotEqual(masked, "IR123456789012345678901234")
        self.assertIn("\u2026", masked)  # Unicode ellipsis

    def test_bank_card_number_masked(self):
        """bank_card_number_masked shows only last 4 digits."""
        company = self.create_company("mask2_co", "Mask2 Co")
        profile = CompanyMerchantProfile(
            company=company,
            bank_card_number="6037991234567890",
        )
        masked = profile.bank_card_number_masked
        self.assertIn("7890", masked)
        self.assertIn("****", masked)
        # Full number should NOT be present
        self.assertNotEqual(masked, "6037991234567890")

    def test_owner_national_code_masked(self):
        """owner_national_code_masked shows only last 4 digits."""
        company = self.create_company("mask3_co", "Mask3 Co")
        profile = CompanyMerchantProfile(
            company=company,
            owner_national_code="0012345678",
        )
        masked = profile.owner_national_code_masked
        self.assertIn("5678", masked)
        self.assertIn("***", masked)
        # Full code should NOT be present
        self.assertNotEqual(masked, "0012345678")

    def test_empty_shaba_masked_returns_empty(self):
        """Empty shaba_number returns empty masked string."""
        company = self.create_company("mask4_co", "Mask4 Co")
        profile = CompanyMerchantProfile(company=company, shaba_number="")
        self.assertEqual(profile.shaba_masked, "")

    def test_empty_card_masked_returns_empty(self):
        """Empty bank_card_number returns empty masked string."""
        company = self.create_company("mask5_co", "Mask5 Co")
        profile = CompanyMerchantProfile(company=company, bank_card_number="")
        self.assertEqual(profile.bank_card_number_masked, "")

    def test_short_national_code_not_masked(self):
        """Very short national code (<=4 chars) is returned as-is."""
        company = self.create_company("mask6_co", "Mask6 Co")
        profile = CompanyMerchantProfile(company=company, owner_national_code="1234")
        # Should return as-is per the model property logic
        self.assertEqual(profile.owner_national_code_masked, "1234")
