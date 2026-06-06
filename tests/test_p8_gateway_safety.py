"""
P8-GATEWAY-SAFETY: Payment Gateway Safety Scaffold Tests.

Covers:
1. Invalid callback does not mark invoice paid
2. Callback with wrong amount does not mark invoice paid (amount tampering)
3. Duplicate valid callback marks invoice paid only once
4. Expired payment callback is rejected
5. Inactive gateway cannot initiate payment
6. Company without approved KYC cannot initiate gateway payment
7. Fake/manual/cash flows from P7 still pass
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.tenants.models import Company, CompanyFinancialPolicy
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentAttempt, PaymentGateway
from apps.payouts.models import TechnicianLedgerEntry, CompanyPlatformFeeEntry


# =============================================================================
# TEST HELPERS
# =============================================================================

class GatewayTestMixin:
    """Shared helpers for gateway safety tests."""

    def create_company(self, code="gw_co", name="Gateway Test Co"):
        return Company.objects.create(code=code, name=name, slug=code, is_active=True)

    def create_user(self, company, role, username=None):
        username = username or f"{role.lower()}_{company.code}_{CompanyUser.objects.count()}"
        return CompanyUser.objects.create_user(
            username=username,
            password="testpass123",
            company=company,
            role=role,
        )

    def create_technician(self, company, service_pct=60, goods_pct=10, travel_pct=100):
        user = self.create_user(company, UserRole.TECHNICIAN)
        return Technician.objects.create(
            company=company,
            user=user,
            service_wage_percent=Decimal(str(service_pct)),
            goods_wage_percent=Decimal(str(goods_pct)),
            travel_wage_percent=Decimal(str(travel_pct)),
        )

    def create_order(self, company, technician=None):
        return Order.objects.create(
            company=company,
            title="Gateway Test Order",
            technician=technician,
            status=Order.Status.DONE,
        )

    def create_issued_invoice(self, company, technician=None, total=10000000):
        order = self.create_order(company, technician=technician)
        invoice = Invoice.objects.create(
            company=company,
            order=order,
            invoice_number=f"INV-{company.code.upper()}-{Invoice.objects.count() + 1:05d}",
            status=Invoice.Status.ISSUED,
            issued_at=timezone.now(),
            subtotal=total,
            total_amount=total,
            net_amount_before_invoice_discounts=total,
            gross_amount=total,
            technician_service_wage_percent_snapshot=Decimal("60") if technician else Decimal("0"),
            technician_goods_wage_percent_snapshot=Decimal("10") if technician else Decimal("0"),
            technician_travel_wage_percent_snapshot=Decimal("100") if technician else Decimal("0"),
        )
        InvoiceItem.objects.create(
            company=company,
            invoice=invoice,
            description="خدمات تست",
            row_type=InvoiceItem.RowType.SERVICE,
            quantity=1,
            unit_price=total,
            total_price=total,
        )
        return invoice

    def create_financial_policy(self, company, fee_percent=1):
        policy, _ = CompanyFinancialPolicy.objects.get_or_create(
            company=company,
            defaults={
                "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
                "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
                "platform_fee_percent": Decimal(str(fee_percent)),
            },
        )
        policy.platform_fee_percent = Decimal(str(fee_percent))
        policy.save(update_fields=["platform_fee_percent"])
        return policy

    def create_fake_gateway(self, company, active=True, default=True):
        gateway, _ = PaymentGateway.objects.get_or_create(
            company=company,
            gateway_type=PaymentGateway.GatewayType.FAKE,
            defaults={
                "name": "Fake Gateway",
                "is_active": active,
                "is_default": default,
            },
        )
        gateway.is_active = active
        gateway.is_default = default
        gateway.save(update_fields=["is_active", "is_default"])
        return gateway

    def create_pending_payment(self, company, invoice, gateway, reference_id="SUCCESS-test123"):
        """Create a Payment in PENDING state simulating post-initiation."""
        return Payment.objects.create(
            company=company,
            invoice=invoice,
            gateway=gateway,
            amount=invoice.total_amount,
            status=Payment.Status.PENDING,
            reference_id=reference_id,
        )


# =============================================================================
# 1. INVALID CALLBACK TESTS
# =============================================================================

class InvalidCallbackTest(TestCase, GatewayTestMixin):
    """Verify that invalid callbacks do not mark invoice as paid."""

    def setUp(self):
        self.company = self.create_company("inv_cb", "Invalid CB Co")
        self.tech = self.create_technician(self.company)
        self.policy = self.create_financial_policy(self.company)
        self.gateway = self.create_fake_gateway(self.company)
        self.invoice = self.create_issued_invoice(self.company, technician=self.tech)

    def test_callback_with_nonexistent_reference_id_fails(self):
        """Callback with unknown reference_id should not mark anything as paid."""
        from apps.payments.services import PaymentCallbackService

        success, msg, payment = PaymentCallbackService.handle_callback(
            company=self.company,
            reference_id="NONEXISTENT-abc123",
        )
        self.assertFalse(success)
        self.assertIsNone(payment)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)

    def test_callback_with_empty_reference_id_fails(self):
        """Empty reference_id should be rejected immediately."""
        from apps.payments.services import PaymentCallbackService

        success, msg, payment = PaymentCallbackService.handle_callback(
            company=self.company,
            reference_id="",
        )
        self.assertFalse(success)
        self.assertIsNone(payment)

    def test_callback_with_failed_reference_does_not_pay(self):
        """FAIL-prefixed reference causes FakeProvider to return failure."""
        from apps.payments.services import PaymentCallbackService

        payment = self.create_pending_payment(
            self.company, self.invoice, self.gateway,
            reference_id="FAIL-test123",
        )
        success, msg, result = PaymentCallbackService.handle_callback(
            company=self.company,
            reference_id="FAIL-test123",
        )
        self.assertFalse(success)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)


# =============================================================================
# 2. AMOUNT TAMPERING TESTS
# =============================================================================

class AmountTamperingTest(TestCase, GatewayTestMixin):
    """Verify that amount mismatch between provider response and Payment is rejected."""

    def setUp(self):
        self.company = self.create_company("tamp_co", "Tamper Co")
        self.tech = self.create_technician(self.company)
        self.policy = self.create_financial_policy(self.company)
        self.gateway = self.create_fake_gateway(self.company)
        self.invoice = self.create_issued_invoice(self.company, technician=self.tech, total=5000000)

    def test_mismatched_amount_rejects_payment(self):
        """If provider reports different amount than expected, payment is rejected."""
        from apps.payments.services import PaymentVerifyService
        from apps.payments.providers.base import VerificationResponse

        payment = self.create_pending_payment(
            self.company, self.invoice, self.gateway,
            reference_id="SUCCESS-tamper1",
        )

        # Mock the provider to return a different verified_amount
        tampered_response = VerificationResponse(
            success=True,
            tracking_code="TRACK-tampered",
            verified_amount=1000,  # Much less than 5,000,000
            raw_response={"status": "verified", "amount": 1000},
        )

        with patch("apps.payments.services.get_provider") as mock_get_provider:
            mock_provider = mock_get_provider.return_value
            mock_provider.verify_payment.return_value = tampered_response

            success, msg = PaymentVerifyService.verify(payment=payment)

        self.assertFalse(success)
        self.assertIn("mismatch", msg.lower())
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)

    def test_matching_amount_allows_payment(self):
        """If provider returns same amount, payment proceeds normally."""
        from apps.payments.services import PaymentCallbackService

        payment = self.create_pending_payment(
            self.company, self.invoice, self.gateway,
            reference_id="SUCCESS-match1",
        )
        success, msg, result = PaymentCallbackService.handle_callback(
            company=self.company,
            reference_id="SUCCESS-match1",
        )
        self.assertTrue(success)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)


# =============================================================================
# 3. DUPLICATE CALLBACK TESTS
# =============================================================================

class DuplicateCallbackTest(TestCase, GatewayTestMixin):
    """Verify that duplicate callbacks only process payment once."""

    def setUp(self):
        self.company = self.create_company("dup_cb", "Dup CB Co")
        self.tech = self.create_technician(self.company)
        self.policy = self.create_financial_policy(self.company)
        self.gateway = self.create_fake_gateway(self.company)
        self.invoice = self.create_issued_invoice(self.company, technician=self.tech)

    def test_duplicate_callback_does_not_double_pay(self):
        """Calling handle_callback twice with same reference marks PAID only once."""
        from apps.payments.services import PaymentCallbackService

        payment = self.create_pending_payment(
            self.company, self.invoice, self.gateway,
            reference_id="SUCCESS-dup1",
        )

        # First callback
        success1, msg1, _ = PaymentCallbackService.handle_callback(
            company=self.company,
            reference_id="SUCCESS-dup1",
        )
        self.assertTrue(success1)

        # Second callback (duplicate)
        success2, msg2, _ = PaymentCallbackService.handle_callback(
            company=self.company,
            reference_id="SUCCESS-dup1",
        )
        self.assertTrue(success2)  # idempotent success
        self.assertIn("already", msg2.lower())

        # Only one PAID payment should exist
        paid_count = Payment.objects.filter(
            company=self.company, invoice=self.invoice, status=Payment.Status.PAID
        ).count()
        self.assertEqual(paid_count, 1)

    def test_duplicate_callback_does_not_duplicate_ledger(self):
        """Duplicate callback does not create duplicate technician ledger entries."""
        from apps.payments.services import PaymentCallbackService

        payment = self.create_pending_payment(
            self.company, self.invoice, self.gateway,
            reference_id="SUCCESS-dup2",
        )

        PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-dup2",
        )
        PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-dup2",
        )

        credit_count = TechnicianLedgerEntry.objects.filter(
            company=self.company,
            technician=self.tech,
            entry_type=TechnicianLedgerEntry.EntryType.CREDIT,
        ).count()
        self.assertEqual(credit_count, 1)

    def test_duplicate_callback_does_not_duplicate_platform_fee(self):
        """Duplicate callback does not create duplicate platform fee entries."""
        from apps.payments.services import PaymentCallbackService

        payment = self.create_pending_payment(
            self.company, self.invoice, self.gateway,
            reference_id="SUCCESS-dup3",
        )

        PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-dup3",
        )
        PaymentCallbackService.handle_callback(
            company=self.company, reference_id="SUCCESS-dup3",
        )

        fee_count = CompanyPlatformFeeEntry.objects.filter(
            company=self.company,
            entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT,
        ).count()
        self.assertEqual(fee_count, 1)


# =============================================================================
# 4. PAYMENT EXPIRATION TESTS
# =============================================================================

class PaymentExpirationTest(TestCase, GatewayTestMixin):
    """Verify that expired payments are rejected even with valid callback."""

    def setUp(self):
        self.company = self.create_company("exp_co", "Expiry Co")
        self.tech = self.create_technician(self.company)
        self.policy = self.create_financial_policy(self.company)
        self.gateway = self.create_fake_gateway(self.company)
        self.invoice = self.create_issued_invoice(self.company, technician=self.tech)

    @override_settings(PAYMENT_EXPIRATION_MINUTES=30)
    def test_expired_payment_callback_is_rejected(self):
        """Payment older than PAYMENT_EXPIRATION_MINUTES is rejected."""
        from apps.payments.services import PaymentCallbackService

        payment = self.create_pending_payment(
            self.company, self.invoice, self.gateway,
            reference_id="SUCCESS-expired1",
        )
        # Backdate created_at to simulate expiration
        old_time = timezone.now() - timedelta(minutes=60)
        Payment.objects.filter(pk=payment.pk).update(created_at=old_time)

        success, msg, result = PaymentCallbackService.handle_callback(
            company=self.company,
            reference_id="SUCCESS-expired1",
        )
        self.assertFalse(success)
        self.assertIn("expired", msg.lower())

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.invoice.refresh_from_db()
        self.assertEqual(self.invoice.status, Invoice.Status.ISSUED)

    @override_settings(PAYMENT_EXPIRATION_MINUTES=30)
    def test_fresh_payment_callback_is_accepted(self):
        """Payment within expiration window is accepted normally."""
        from apps.payments.services import PaymentCallbackService

        payment = self.create_pending_payment(
            self.company, self.invoice, self.gateway,
            reference_id="SUCCESS-fresh1",
        )
        # created_at is now() by default — well within 30 min

        success, msg, _ = PaymentCallbackService.handle_callback(
            company=self.company,
            reference_id="SUCCESS-fresh1",
        )
        self.assertTrue(success)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)


# =============================================================================
# 5. INACTIVE GATEWAY TESTS
# =============================================================================

class InactiveGatewayTest(TestCase, GatewayTestMixin):
    """Verify that inactive gateway cannot be used to initiate payments."""

    def setUp(self):
        self.company = self.create_company("inact_co", "Inactive GW Co")
        self.tech = self.create_technician(self.company)
        self.policy = self.create_financial_policy(self.company)
        self.invoice = self.create_issued_invoice(self.company, technician=self.tech)

    def test_inactive_gateway_cannot_initiate_payment(self):
        """PaymentStartService rejects inactive gateway."""
        from apps.payments.services import PaymentStartService

        gateway = self.create_fake_gateway(self.company, active=False)

        with self.assertRaises(ValueError) as ctx:
            PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
                gateway=gateway,
            )
        self.assertIn("not active", str(ctx.exception).lower())

    def test_no_gateway_configured_raises(self):
        """If no gateway exists, PaymentStartService raises."""
        from apps.payments.services import PaymentStartService

        # No gateway created for this company
        with self.assertRaises(ValueError) as ctx:
            PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
            )
        self.assertIn("no active", str(ctx.exception).lower())


# =============================================================================
# 6. KYC GUARD TESTS
# =============================================================================

class KYCGuardPaymentTest(TestCase, GatewayTestMixin):
    """Verify that company without KYC approval cannot initiate gateway payments."""

    def setUp(self):
        self.company = self.create_company("kyc_gw", "KYC GW Co")
        self.tech = self.create_technician(self.company)
        self.policy = self.create_financial_policy(self.company)
        self.gateway = self.create_fake_gateway(self.company, active=True)
        self.invoice = self.create_issued_invoice(self.company, technician=self.tech)

    def test_no_kyc_profile_blocks_payment_initiation(self):
        """Company without merchant profile cannot start gateway payment."""
        from apps.payments.services import PaymentStartService

        with self.assertRaises(ValueError) as ctx:
            PaymentStartService.start(
                invoice=self.invoice,
                callback_url="https://example.com/callback/",
                gateway=self.gateway,
            )
        self.assertIn("eligible", str(ctx.exception).lower())

    def test_approved_kyc_allows_payment_initiation(self):
        """Company with approved KYC can start gateway payment."""
        from apps.payments.services import PaymentStartService
        from apps.tenants.models import CompanyMerchantProfile

        # Create approved KYC
        CompanyMerchantProfile.objects.create(
            company=self.company,
            status=CompanyMerchantProfile.Status.APPROVED,
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
            national_card_image="test_file.jpg",
        )

        payment, attempt, redirect_url = PaymentStartService.start(
            invoice=self.invoice,
            callback_url="https://example.com/callback/",
            gateway=self.gateway,
        )
        self.assertIsNotNone(payment)
        self.assertEqual(payment.status, Payment.Status.PENDING)
        self.assertTrue(redirect_url.startswith("https://"))


# =============================================================================
# 7. CASH/MANUAL FLOW REGRESSION (P7 compatibility)
# =============================================================================

class CashFlowRegressionTest(TestCase, GatewayTestMixin):
    """Ensure P8 changes did not break existing cash/manual payment flows."""

    def setUp(self):
        self.company = self.create_company("cash_reg", "Cash Reg Co")
        self.tech = self.create_technician(self.company)
        self.policy = self.create_financial_policy(self.company)

    def test_cash_company_payment_still_works(self):
        """mark_paid with cash method (no gateway) still works."""
        from apps.invoices.services import InvoiceMarkPaidService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = Payment.objects.create(
            company=self.company,
            invoice=invoice,
            amount=invoice.total_amount,
            status=Payment.Status.PAID,
            metadata={"payment_source": "CASH_RECEIVED_BY_COMPANY", "method": "cash"},
        )
        InvoiceMarkPaidService.mark_paid(invoice=invoice, payment=payment, payment_method="cash")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

    def test_cash_technician_payment_still_works(self):
        """mark_paid with technician cash still creates correct ledger entries."""
        from apps.invoices.services import InvoiceMarkPaidService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = Payment.objects.create(
            company=self.company,
            invoice=invoice,
            amount=invoice.total_amount,
            status=Payment.Status.PAID,
            metadata={
                "payment_source": "CASH_RECEIVED_BY_TECHNICIAN",
                "method": "cash",
                "technician_id": self.tech.id,
            },
        )
        InvoiceMarkPaidService.mark_paid(invoice=invoice, payment=payment, payment_method="cash")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)

        # Verify ledger entries
        credits = TechnicianLedgerEntry.objects.filter(
            company=self.company, technician=self.tech,
            entry_type=TechnicianLedgerEntry.EntryType.CREDIT,
        )
        debits = TechnicianLedgerEntry.objects.filter(
            company=self.company, technician=self.tech,
            entry_type=TechnicianLedgerEntry.EntryType.DEBIT,
        )
        self.assertEqual(credits.count(), 1)
        self.assertEqual(debits.count(), 1)

    def test_manual_mark_paid_without_payment_object_works(self):
        """mark_paid without Payment object (legacy admin flow) still works."""
        from apps.invoices.services import InvoiceMarkPaidService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        InvoiceMarkPaidService.mark_paid(invoice=invoice, payment_method="cash")
        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.PAID)
        self.assertIsNotNone(invoice.settled_at)

    def test_platform_fee_recorded_for_cash_payment(self):
        """Platform fee is correctly recorded for cash payments."""
        from apps.invoices.services import InvoiceMarkPaidService

        invoice = self.create_issued_invoice(self.company, technician=self.tech, total=10000000)
        InvoiceMarkPaidService.mark_paid(invoice=invoice, payment_method="cash")

        fee_entries = CompanyPlatformFeeEntry.objects.filter(
            company=self.company,
            entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT,
        )
        self.assertEqual(fee_entries.count(), 1)
        # 1% of 10,000,000 = 100,000
        self.assertEqual(fee_entries.first().amount_rial, 100000)
