"""
P11-PAYMENT-EXPIRATION-CLEANUP: Tests for expired payment cleanup service and command.

Covers:
1. Dry-run does not change payment status
2. Old pending gateway payment is marked FAILED
3. Fresh pending gateway payment is not changed
4. PAID payment is not changed
5. Manual/cash payment (no gateway) is not changed
6. Invoice remains unpaid when payment expires
7. No technician ledger entry is created
8. No platform fee entry is created
9. Running cleanup twice is idempotent
10. Management command dry-run/real output
"""
from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.test import TestCase, override_settings
from django.core.management import call_command
from django.utils import timezone

from apps.accounts.models import CompanyUser, Technician, UserRole
from apps.tenants.models import Company, CompanyFinancialPolicy
from apps.invoices.models import Invoice, InvoiceItem
from apps.orders.models import Order
from apps.payments.models import Payment, PaymentGateway
from apps.payouts.models import TechnicianLedgerEntry, CompanyPlatformFeeEntry


class ExpirationTestMixin:
    """Shared helpers."""

    def create_company(self, code="exp_co", name="Expiration Test Co"):
        return Company.objects.create(code=code, name=name, slug=code, is_active=True)

    def create_technician(self, company):
        user = CompanyUser.objects.create_user(
            username=f"tech_{company.code}_{CompanyUser.objects.count()}",
            password="testpass123",
            company=company,
            role=UserRole.TECHNICIAN,
        )
        return Technician.objects.create(
            company=company,
            user=user,
            service_wage_percent=Decimal("60"),
            goods_wage_percent=Decimal("10"),
            travel_wage_percent=Decimal("100"),
        )

    def create_issued_invoice(self, company, technician=None, total=10000000):
        order = Order.objects.create(
            company=company, title="Test Order", technician=technician, status=Order.Status.DONE,
        )
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
        )
        InvoiceItem.objects.create(
            company=company, invoice=invoice, description="Test",
            row_type=InvoiceItem.RowType.SERVICE, quantity=1, unit_price=total, total_price=total,
        )
        return invoice

    def create_fake_gateway(self, company):
        gateway, _ = PaymentGateway.objects.get_or_create(
            company=company,
            gateway_type=PaymentGateway.GatewayType.FAKE,
            defaults={"name": "Fake GW", "is_active": True, "is_default": True},
        )
        return gateway

    def create_pending_payment(self, company, invoice, gateway, age_minutes=60):
        """Create a PENDING gateway payment backdated by age_minutes."""
        payment = Payment.objects.create(
            company=company,
            invoice=invoice,
            gateway=gateway,
            amount=invoice.total_amount,
            status=Payment.Status.PENDING,
            reference_id=f"SUCCESS-exp-{Payment.objects.count()}",
        )
        # Backdate created_at
        old_time = timezone.now() - timedelta(minutes=age_minutes)
        Payment.objects.filter(pk=payment.pk).update(created_at=old_time)
        payment.refresh_from_db()
        return payment

    def create_cash_payment(self, company, invoice, age_minutes=60):
        """Create a cash/manual payment (no gateway) backdated."""
        payment = Payment.objects.create(
            company=company,
            invoice=invoice,
            gateway=None,
            amount=invoice.total_amount,
            status=Payment.Status.PENDING,
            metadata={"payment_source": "CASH_RECEIVED_BY_COMPANY", "method": "cash"},
        )
        old_time = timezone.now() - timedelta(minutes=age_minutes)
        Payment.objects.filter(pk=payment.pk).update(created_at=old_time)
        payment.refresh_from_db()
        return payment


# =============================================================================
# SERVICE TESTS
# =============================================================================

@override_settings(PAYMENT_EXPIRATION_MINUTES=30)
class PaymentExpirationServiceTest(TestCase, ExpirationTestMixin):
    """Test PaymentExpirationService.expire_old_pending_payments."""

    def setUp(self):
        self.company = self.create_company()
        self.tech = self.create_technician(self.company)
        self.gateway = self.create_fake_gateway(self.company)
        CompanyFinancialPolicy.objects.get_or_create(
            company=self.company,
            defaults={"platform_fee_percent": Decimal("1")},
        )

    def test_dry_run_does_not_change_status(self):
        """Dry-run should NOT change any payment status."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=60)

        result = PaymentExpirationService.expire_old_pending_payments(dry_run=True)

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["expired"], 1)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING, "Dry-run must not change status")

    def test_old_pending_gateway_payment_is_expired(self):
        """Old pending gateway payment should be marked FAILED."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=60)

        result = PaymentExpirationService.expire_old_pending_payments()

        self.assertEqual(result["expired"], 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
        self.assertTrue(payment.metadata.get("expired_by_cleanup"))

    def test_fresh_pending_payment_is_not_changed(self):
        """Payment within expiration window should NOT be changed."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        # Fresh: only 5 minutes old (threshold is 30)
        payment = self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=5)

        result = PaymentExpirationService.expire_old_pending_payments()

        self.assertEqual(result["expired"], 0)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_paid_payment_is_not_changed(self):
        """PAID payment should never be changed by cleanup."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = Payment.objects.create(
            company=self.company,
            invoice=invoice,
            gateway=self.gateway,
            amount=invoice.total_amount,
            status=Payment.Status.PAID,
            reference_id="SUCCESS-paid",
            paid_at=timezone.now() - timedelta(minutes=60),
        )
        old_time = timezone.now() - timedelta(minutes=60)
        Payment.objects.filter(pk=payment.pk).update(created_at=old_time)

        result = PaymentExpirationService.expire_old_pending_payments()

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PAID)
        self.assertEqual(result["expired"], 0)

    def test_cash_payment_without_gateway_not_changed(self):
        """Manual/cash payments (no gateway) should NOT be affected."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = self.create_cash_payment(self.company, invoice, age_minutes=60)

        result = PaymentExpirationService.expire_old_pending_payments()

        self.assertEqual(result["expired"], 0)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_invoice_remains_unpaid(self):
        """When payment expires, invoice should NOT become PAID."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=60)

        PaymentExpirationService.expire_old_pending_payments()

        invoice.refresh_from_db()
        self.assertEqual(invoice.status, Invoice.Status.ISSUED)

    def test_no_technician_ledger_created(self):
        """Expiration should NOT create any technician ledger entries."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=60)

        before_count = TechnicianLedgerEntry.objects.filter(company=self.company).count()
        PaymentExpirationService.expire_old_pending_payments()
        after_count = TechnicianLedgerEntry.objects.filter(company=self.company).count()

        self.assertEqual(before_count, after_count)

    def test_no_platform_fee_created(self):
        """Expiration should NOT create any platform fee entries."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=60)

        before_count = CompanyPlatformFeeEntry.objects.filter(company=self.company).count()
        PaymentExpirationService.expire_old_pending_payments()
        after_count = CompanyPlatformFeeEntry.objects.filter(company=self.company).count()

        self.assertEqual(before_count, after_count)

    def test_running_twice_is_idempotent(self):
        """Running cleanup twice should not change results or create errors."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=60)

        result1 = PaymentExpirationService.expire_old_pending_payments()
        result2 = PaymentExpirationService.expire_old_pending_payments()

        self.assertEqual(result1["expired"], 1)
        self.assertEqual(result2["expired"], 0)  # Already failed, not pending anymore

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_initiated_payment_is_also_expired(self):
        """INITIATED (never went to PENDING) old payments should also be expired."""
        from apps.payments.services_expiration import PaymentExpirationService

        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = Payment.objects.create(
            company=self.company,
            invoice=invoice,
            gateway=self.gateway,
            amount=invoice.total_amount,
            status=Payment.Status.INITIATED,
        )
        old_time = timezone.now() - timedelta(minutes=60)
        Payment.objects.filter(pk=payment.pk).update(created_at=old_time)

        result = PaymentExpirationService.expire_old_pending_payments()

        self.assertEqual(result["expired"], 1)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)


# =============================================================================
# MANAGEMENT COMMAND TESTS
# =============================================================================

@override_settings(PAYMENT_EXPIRATION_MINUTES=30)
class ExpirePendingPaymentsCommandTest(TestCase, ExpirationTestMixin):
    """Test the expire_pending_payments management command."""

    def setUp(self):
        self.company = self.create_company("cmd_co", "Command Test Co")
        self.tech = self.create_technician(self.company)
        self.gateway = self.create_fake_gateway(self.company)

    def test_command_dry_run(self):
        """Management command --dry-run should output counts without changing data."""
        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=60)

        out = StringIO()
        call_command("expire_pending_payments", "--dry-run", stdout=out)

        output = out.getvalue()
        self.assertIn("DRY RUN", output)
        self.assertIn("1", output)  # expired count

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

    def test_command_real_run(self):
        """Management command without --dry-run should actually expire payments."""
        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        payment = self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=60)

        out = StringIO()
        call_command("expire_pending_payments", stdout=out)

        output = out.getvalue()
        self.assertIn("Done", output)

        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)

    def test_command_with_minutes_override(self):
        """Command --minutes flag overrides default threshold."""
        invoice = self.create_issued_invoice(self.company, technician=self.tech)
        # 45 minutes old
        payment = self.create_pending_payment(self.company, invoice, self.gateway, age_minutes=45)

        out = StringIO()
        # Threshold 60 min → should NOT expire (45 < 60)
        call_command("expire_pending_payments", "--minutes", "60", stdout=out)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.PENDING)

        # Threshold 30 min → should expire (45 > 30)
        call_command("expire_pending_payments", "--minutes", "30", stdout=out)
        payment.refresh_from_db()
        self.assertEqual(payment.status, Payment.Status.FAILED)
