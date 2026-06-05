"""
Financial Report Views — Payment P6.

Six company-admin report pages:
  1. financial_summary         /<code>/admin/financial-reports/summary/
  2. technician_breakdown      /<code>/admin/financial-reports/technicians/
  3. invoice_settlement_detail /<code>/admin/financial-reports/invoices/
  4. cash_control              /<code>/admin/financial-reports/cash-control/
  5. platform_fee_report       /<code>/admin/financial-reports/platform-fees/
  6. audit_report              /<code>/admin/financial-reports/audit/
"""
from __future__ import annotations

from django.db.models import Sum, Count, Q
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.accounts.permissions import require_tenant_role


# ---------------------------------------------------------------------------
# 1. Summary
# ---------------------------------------------------------------------------

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def financial_summary(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    from apps.invoices.models import Invoice
    from apps.payouts.models import TechnicianLedgerEntry, CompanyPlatformFeeEntry
    from apps.payouts.services_platform_fee import PlatformFeeService

    inv_qs = Invoice.objects.filter(company=company)
    paid_qs = inv_qs.filter(status=Invoice.Status.PAID)

    total_invoiced = paid_qs.aggregate(t=Sum("total_amount"))["t"] or 0
    total_invoices = paid_qs.count()

    # Technician ledger totals
    tl_qs = TechnicianLedgerEntry.objects.filter(company=company)
    tech_credits = tl_qs.filter(entry_type=TechnicianLedgerEntry.EntryType.CREDIT).aggregate(t=Sum("amount_rial"))["t"] or 0
    tech_debits = tl_qs.filter(entry_type=TechnicianLedgerEntry.EntryType.DEBIT).aggregate(t=Sum("amount_rial"))["t"] or 0
    tech_net_owed = int(tech_credits) - int(tech_debits)

    # Platform fee
    platform_fee_balance = PlatformFeeService.get_balance(company)
    pf_qs = CompanyPlatformFeeEntry.objects.filter(company=company)
    platform_fee_total_accrued = pf_qs.filter(entry_type=CompanyPlatformFeeEntry.EntryType.DEBIT).aggregate(t=Sum("amount_rial"))["t"] or 0
    platform_fee_total_settled = pf_qs.filter(entry_type=CompanyPlatformFeeEntry.EntryType.CREDIT).aggregate(t=Sum("amount_rial"))["t"] or 0

    return render(request, "tenants/financial_reports/summary.html", {
        "company": company,
        "total_invoiced": total_invoiced,
        "total_invoices": total_invoices,
        "tech_credits": tech_credits,
        "tech_debits": tech_debits,
        "tech_net_owed": tech_net_owed,
        "platform_fee_balance": platform_fee_balance,
        "platform_fee_total_accrued": platform_fee_total_accrued,
        "platform_fee_total_settled": platform_fee_total_settled,
    })


# ---------------------------------------------------------------------------
# 2. Technician Breakdown
# ---------------------------------------------------------------------------

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_breakdown(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    from apps.payouts.models import TechnicianLedgerEntry
    from apps.payouts.services import TechnicianLedgerService
    from apps.accounts.models import Technician

    technicians = Technician.objects.filter(company=company).select_related("user")
    rows = []
    for tech in technicians:
        balance = TechnicianLedgerService.get_balance(company, tech)
        credit = (
            TechnicianLedgerEntry.objects.filter(company=company, technician=tech, entry_type=TechnicianLedgerEntry.EntryType.CREDIT)
            .aggregate(t=Sum("amount_rial"))["t"] or 0
        )
        debit = (
            TechnicianLedgerEntry.objects.filter(company=company, technician=tech, entry_type=TechnicianLedgerEntry.EntryType.DEBIT)
            .aggregate(t=Sum("amount_rial"))["t"] or 0
        )
        rows.append({
            "technician": tech,
            "credit": credit,
            "debit": debit,
            "balance": balance,
        })

    return render(request, "tenants/financial_reports/technician_breakdown.html", {
        "company": company,
        "rows": rows,
    })


# ---------------------------------------------------------------------------
# 3. Invoice Settlement Detail
# ---------------------------------------------------------------------------

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def invoice_settlement_detail(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    from apps.invoices.models import Invoice

    invoices = (
        Invoice.objects.filter(company=company, status=Invoice.Status.PAID)
        .select_related("order__technician__user")
        .order_by("-paid_at", "-id")[:200]
    )

    return render(request, "tenants/financial_reports/invoice_settlement_detail.html", {
        "company": company,
        "invoices": invoices,
    })


# ---------------------------------------------------------------------------
# 4. Cash Control
# ---------------------------------------------------------------------------

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def cash_control(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    from apps.payouts.models import TechnicianLedgerEntry

    # Cash received by technician: entries with source=CASH_FROM_CUSTOMER
    tech_cash_qs = TechnicianLedgerEntry.objects.filter(
        company=company,
        source=TechnicianLedgerEntry.Source.CASH_FROM_CUSTOMER,
        entry_type=TechnicianLedgerEntry.EntryType.DEBIT,
    ).select_related("technician__user", "invoice").order_by("-created_at")[:200]

    tech_cash_total = tech_cash_qs.aggregate(t=Sum("amount_rial"))["t"] or 0

    return render(request, "tenants/financial_reports/cash_control.html", {
        "company": company,
        "tech_cash_entries": tech_cash_qs,
        "tech_cash_total": tech_cash_total,
    })


# ---------------------------------------------------------------------------
# 5. Platform Fee Report
# ---------------------------------------------------------------------------

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def platform_fee_report(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    from apps.payouts.services_platform_fee import PlatformFeeService

    balance = PlatformFeeService.get_balance(company)
    entries = PlatformFeeService.list_entries(company)

    return render(request, "tenants/financial_reports/platform_fee_report.html", {
        "company": company,
        "balance": balance,
        "entries": entries,
    })


# ---------------------------------------------------------------------------
# 6. Audit / Inconsistency Report
# ---------------------------------------------------------------------------

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def audit_report(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    from apps.invoices.models import Invoice
    from apps.payouts.models import TechnicianLedgerEntry, CompanyPlatformFeeEntry

    # Paid invoices missing technician ledger credit entry
    paid_invoices = Invoice.objects.filter(company=company, status=Invoice.Status.PAID)
    invoices_with_ledger = (
        TechnicianLedgerEntry.objects
        .filter(company=company, invoice__in=paid_invoices, entry_type=TechnicianLedgerEntry.EntryType.CREDIT)
        .values_list("invoice_id", flat=True)
    )
    missing_tech_ledger = paid_invoices.exclude(id__in=invoices_with_ledger)

    # Paid invoices missing platform fee entry (where policy has a fee)
    invoices_with_fee_entry = (
        CompanyPlatformFeeEntry.objects
        .filter(company=company, invoice__in=paid_invoices)
        .values_list("invoice_id", flat=True)
    )
    missing_platform_fee = paid_invoices.exclude(id__in=invoices_with_fee_entry)

    return render(request, "tenants/financial_reports/audit_report.html", {
        "company": company,
        "missing_tech_ledger": missing_tech_ledger[:100],
        "missing_platform_fee": missing_platform_fee[:100],
        "missing_tech_ledger_count": missing_tech_ledger.count(),
        "missing_platform_fee_count": missing_platform_fee.count(),
    })
