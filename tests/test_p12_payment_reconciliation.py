"""
P12-PAYMENT-RECONCILIATION-SCAFFOLD: Reconciliation Service Tests.

Covers:
1. Matching provider row → matched
2. Provider paid but internal pending → status mismatch
3. Provider amount differs → amount mismatch
4. Provider row missing internal payment → missing_in_internal
5. Internal payment missing from provider → missing_in_provider
6. Duplicate provider reference rows detected
7. Invalid CSV missing columns fails safely
8. Command dry-run parses and prints summary
9. No invoice marked paid
10. No ledger entries created
11. No platform fee entries created
12. Cash/manual payments are ignored
"""
import os
import tempfile
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

from apps.payments.services_reconciliation import (
    PaymentReconciliationService,
    ProviderReportRow,
    parse_reconciliation_csv,
)


class ReconciliationTestMixin:
    """Shared helpers."""

    def create_company(self, code="recon_co"):
        return Company.objects.create(code=code, name="Recon Co", slug=code, is_active=True)

    def create_technician(self, company):
        user = CompanyUser.objects.create_user(
            username=f"tech_{company.code}_{CompanyUser.objects.count()}",
            password="testpass123", company=company, role=UserRole.TECHNICIAN,
        )
        return Technician.objects.create(
            company=company, user=user, service_wage_percent=Decimal("60"),
        )

    def create_gateway(self, company):
        gw, _ = PaymentGateway.objects.get_or_create(
            company=company, gateway_type=PaymentGateway.GatewayType.FAKE,
            defaults={"name": "Fake GW", "is_active": True, "is_default": True},
        )
        return gw

    def create_issued_invoice(self, company, tech=None, total=5000000):
        order = Order.objects.create(company=company, title="Test", technician=tech, status=Order.Status.DONE)
        inv = Invoice.objects.create(
            company=company, order=order, status=Invoice.Status.ISSUED,
            invoice_number=f"INV-{company.code}-{Invoice.objects.count()+1:05d}",
            issued_at=timezone.now(), subtotal=total, total_amount=total,
            gross_amount=total, net_amount_before_invoice_discounts=total,
            technician_service_wage_percent_snapshot=Decimal("60") if tech else Decimal("0"),
        )
        InvoiceItem.objects.create(
            company=company, invoice=inv, description="svc",
            row_type=InvoiceItem.RowType.SERVICE, quantity=1, unit_price=total, total_price=total,
        )
        return inv

    def create_payment(self, company, invoice, gateway, status="pending", ref="REF-001", amount=None):
        return Payment.objects.create(
            company=company, invoice=invoice, gateway=gateway,
            amount=amount or invoice.total_amount, status=status, reference_id=ref,
        )

    def write_csv(self, rows_text):
        """Write CSV text to a temp file and return path."""
        f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8")
        f.write(rows_text)
        f.close()
        return f.name


# =============================================================================
# SERVICE TESTS
# =============================================================================

class PaymentReconciliationServiceTest(TestCase, ReconciliationTestMixin):
    """Test PaymentReconciliationService.reconcile."""

    def setUp(self):
        self.company = self.create_company()
        self.tech = self.create_technician(self.company)
        self.gw = self.create_gateway(self.company)
        CompanyFinancialPolicy.objects.get_or_create(
            company=self.company, defaults={"platform_fee_percent": Decimal("1")},
        )

    def test_matching_provider_row(self):
        """Provider and internal both PAID with same amount → matched."""
        inv = self.create_issued_invoice(self.company, self.tech)
        self.create_payment(self.company, inv, self.gw, status="paid", ref="REF-MATCH", amount=5000000)

        rows = [ProviderReportRow(provider_reference="REF-MATCH", amount=5000000, status="paid")]
        result = PaymentReconciliationService.reconcile(provider_rows=rows)

        self.assertEqual(result.matched, 1)
        self.assertEqual(result.amount_mismatch, 0)
        self.assertEqual(result.status_mismatch, 0)

    def test_provider_paid_internal_pending_status_mismatch(self):
        """Provider says PAID but internal is PENDING → status_mismatch."""
        inv = self.create_issued_invoice(self.company, self.tech)
        self.create_payment(self.company, inv, self.gw, status="pending", ref="REF-PEND")

        rows = [ProviderReportRow(provider_reference="REF-PEND", amount=5000000, status="paid")]
        result = PaymentReconciliationService.reconcile(provider_rows=rows)

        self.assertEqual(result.status_mismatch, 1)
        self.assertEqual(result.matched, 0)
        issue = [r for r in result.records if r.issue_code == "status_mismatch_provider_paid"]
        self.assertEqual(len(issue), 1)
        self.assertIn("manual review", issue[0].issue_message.lower())

    def test_amount_mismatch_detected(self):
        """Provider amount differs from internal → amount_mismatch."""
        inv = self.create_issued_invoice(self.company, self.tech, total=5000000)
        self.create_payment(self.company, inv, self.gw, status="paid", ref="REF-AMT", amount=5000000)

        rows = [ProviderReportRow(provider_reference="REF-AMT", amount=3000000, status="paid")]
        result = PaymentReconciliationService.reconcile(provider_rows=rows)

        self.assertEqual(result.amount_mismatch, 1)

    def test_missing_in_internal(self):
        """Provider has reference not in our DB → missing_in_internal."""
        rows = [ProviderReportRow(provider_reference="UNKNOWN-REF", amount=1000000, status="paid")]
        result = PaymentReconciliationService.reconcile(provider_rows=rows)

        self.assertEqual(result.missing_in_internal, 1)

    def test_missing_in_provider(self):
        """Internal PENDING payment not in provider report → missing_in_provider."""
        inv = self.create_issued_invoice(self.company, self.tech)
        self.create_payment(self.company, inv, self.gw, status="pending", ref="REF-INTERNAL")

        # Empty provider report
        result = PaymentReconciliationService.reconcile(provider_rows=[])

        self.assertEqual(result.missing_in_provider, 1)

    def test_duplicate_provider_reference(self):
        """Same reference appears twice in provider report → flagged."""
        inv = self.create_issued_invoice(self.company, self.tech)
        self.create_payment(self.company, inv, self.gw, status="paid", ref="REF-DUP")

        rows = [
            ProviderReportRow(provider_reference="REF-DUP", amount=5000000, status="paid"),
            ProviderReportRow(provider_reference="REF-DUP", amount=5000000, status="paid"),
        ]
        result = PaymentReconciliationService.reconcile(provider_rows=rows)

        self.assertEqual(result.duplicate_references, 1)

    def test_no_invoice_marked_paid(self):
        """Reconciliation must NOT mark any invoice as PAID."""
        inv = self.create_issued_invoice(self.company, self.tech)
        self.create_payment(self.company, inv, self.gw, status="pending", ref="REF-NOPAY")

        rows = [ProviderReportRow(provider_reference="REF-NOPAY", amount=5000000, status="paid")]
        PaymentReconciliationService.reconcile(provider_rows=rows)

        inv.refresh_from_db()
        self.assertEqual(inv.status, Invoice.Status.ISSUED)

    def test_no_ledger_entries_created(self):
        """Reconciliation must NOT create technician ledger entries."""
        inv = self.create_issued_invoice(self.company, self.tech)
        self.create_payment(self.company, inv, self.gw, status="pending", ref="REF-NOLEDGER")

        before = TechnicianLedgerEntry.objects.filter(company=self.company).count()
        rows = [ProviderReportRow(provider_reference="REF-NOLEDGER", amount=5000000, status="paid")]
        PaymentReconciliationService.reconcile(provider_rows=rows)
        after = TechnicianLedgerEntry.objects.filter(company=self.company).count()

        self.assertEqual(before, after)

    def test_no_platform_fee_created(self):
        """Reconciliation must NOT create platform fee entries."""
        inv = self.create_issued_invoice(self.company, self.tech)
        self.create_payment(self.company, inv, self.gw, status="pending", ref="REF-NOFEE")

        before = CompanyPlatformFeeEntry.objects.filter(company=self.company).count()
        rows = [ProviderReportRow(provider_reference="REF-NOFEE", amount=5000000, status="paid")]
        PaymentReconciliationService.reconcile(provider_rows=rows)
        after = CompanyPlatformFeeEntry.objects.filter(company=self.company).count()

        self.assertEqual(before, after)

    def test_cash_payments_not_in_missing(self):
        """Cash/manual payments (no gateway) should not show as missing_in_provider."""
        inv = self.create_issued_invoice(self.company, self.tech)
        Payment.objects.create(
            company=self.company, invoice=inv, gateway=None,
            amount=inv.total_amount, status=Payment.Status.PENDING,
            metadata={"method": "cash"},
        )

        result = PaymentReconciliationService.reconcile(provider_rows=[])
        self.assertEqual(result.missing_in_provider, 0)


# =============================================================================
# CSV PARSING TESTS
# =============================================================================

class CSVParsingTest(TestCase, ReconciliationTestMixin):
    """Test CSV file parsing."""

    def test_valid_csv_parsed(self):
        csv_text = "provider_reference,amount,status\nREF-1,5000000,paid\nREF-2,3000000,failed\n"
        path = self.write_csv(csv_text)
        try:
            rows, errors = parse_reconciliation_csv(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(len(errors), 0)
            self.assertEqual(rows[0].provider_reference, "REF-1")
            self.assertEqual(rows[0].amount, 5000000)
        finally:
            os.unlink(path)

    def test_missing_columns_detected(self):
        csv_text = "reference,amount\nREF-1,5000\n"
        path = self.write_csv(csv_text)
        try:
            rows, errors = parse_reconciliation_csv(path)
            self.assertEqual(len(rows), 0)
            self.assertTrue(any("Missing required columns" in e for e in errors))
        finally:
            os.unlink(path)

    def test_invalid_amount_skipped(self):
        csv_text = "provider_reference,amount,status\nREF-1,abc,paid\nREF-2,5000,paid\n"
        path = self.write_csv(csv_text)
        try:
            rows, errors = parse_reconciliation_csv(path)
            self.assertEqual(len(rows), 1)  # Only REF-2
            self.assertTrue(any("invalid amount" in e.lower() for e in errors))
        finally:
            os.unlink(path)

    def test_file_not_found(self):
        rows, errors = parse_reconciliation_csv("/nonexistent/file.csv")
        self.assertEqual(len(rows), 0)
        self.assertTrue(any("not found" in e.lower() for e in errors))


# =============================================================================
# MANAGEMENT COMMAND TESTS
# =============================================================================

class ReconcilePaymentsCommandTest(TestCase, ReconciliationTestMixin):
    """Test reconcile_payments management command."""

    def setUp(self):
        self.company = self.create_company("cmd_recon")
        self.tech = self.create_technician(self.company)
        self.gw = self.create_gateway(self.company)

    def test_command_dry_run_outputs_summary(self):
        """Command should parse CSV and print summary."""
        inv = self.create_issued_invoice(self.company, self.tech)
        self.create_payment(self.company, inv, self.gw, status="paid", ref="CMD-REF-1")

        csv_text = "provider_reference,amount,status\nCMD-REF-1,5000000,paid\n"
        path = self.write_csv(csv_text)
        try:
            out = StringIO()
            call_command("reconcile_payments", "--file", path, stdout=out)
            output = out.getvalue()
            self.assertIn("RECONCILIATION SUMMARY", output)
            self.assertIn("Matched", output)
        finally:
            os.unlink(path)

    def test_command_with_issues_prints_action_required(self):
        """Command should print ACTION REQUIRED when issues exist."""
        csv_text = "provider_reference,amount,status\nNONEXISTENT-REF,9999,paid\n"
        path = self.write_csv(csv_text)
        try:
            out = StringIO()
            call_command("reconcile_payments", "--file", path, stdout=out)
            output = out.getvalue()
            self.assertIn("ACTION REQUIRED", output)
        finally:
            os.unlink(path)

    def test_command_invalid_file_raises(self):
        """Command with non-existent file should raise CommandError."""
        from django.core.management.base import CommandError
        out = StringIO()
        with self.assertRaises(CommandError):
            call_command("reconcile_payments", "--file", "/nonexistent.csv", stdout=out, stderr=StringIO())
