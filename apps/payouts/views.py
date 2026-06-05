"""
Payouts - Views.

Technician ledger and manual settlement pages for company admins.
"""
import uuid

from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import Technician
from apps.common.permissions import require_role, require_tenant

from .services import TechnicianLedgerService

_SETTLEMENT_DIRECTIONS = [
    ("COMPANY_PAID_TECHNICIAN", "شرکت به تکنسین پرداخت کرد"),
    ("TECHNICIAN_PAID_COMPANY", "تکنسین به شرکت پرداخت کرد"),
    ("ADJUSTMENT_CREDIT", "اصلاح بستانکاری"),
    ("ADJUSTMENT_DEBIT", "اصلاح بدهکاری"),
]
_ADJUSTMENT_DIRECTIONS = {"ADJUSTMENT_CREDIT", "ADJUSTMENT_DEBIT"}


@login_required
@require_tenant
@require_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_ledger(request, technician_id: int, company_code=None):
    company = request.company
    technician = get_object_or_404(Technician, id=technician_id, company=company)

    balance = TechnicianLedgerService.get_balance(company, technician)
    entries = TechnicianLedgerService.list_statement(company, technician)

    return render(request, "payouts/technician_ledger.html", {
        "company": company,
        "technician": technician,
        "balance": balance,
        "entries": entries,
    })


@login_required
@require_tenant
@require_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_settlement(request, technician_id: int, company_code=None):
    company = request.company
    technician = get_object_or_404(Technician, id=technician_id, company=company)
    balance = TechnicianLedgerService.get_balance(company, technician)

    if request.method == "POST":
        direction = request.POST.get("direction", "")
        amount_raw = request.POST.get("amount", "").strip()
        reference = request.POST.get("reference", "").strip()
        note = request.POST.get("note", "").strip()
        idempotency_token = request.POST.get("idempotency_token", "").strip()

        errors = []
        valid_directions = {d[0] for d in _SETTLEMENT_DIRECTIONS}
        if direction not in valid_directions:
            errors.append("جهت تسویه نامعتبر است.")

        amount_rial = 0
        try:
            amount_rial = int(amount_raw)
            if amount_rial <= 0:
                errors.append("مبلغ باید بزرگ‌تر از صفر باشد.")
        except (ValueError, TypeError):
            errors.append("مبلغ وارد شده معتبر نیست.")

        if direction in _ADJUSTMENT_DIRECTIONS and not note:
            errors.append("برای تعدیل، توضیحات الزامی است.")

        if not idempotency_token:
            errors.append("توکن یکتا یافت نشد. لطفاً صفحه را رفرش کنید.")

        if errors:
            return render(request, "payouts/technician_settlement.html", {
                "company": company,
                "technician": technician,
                "balance": balance,
                "directions": _SETTLEMENT_DIRECTIONS,
                "errors": errors,
                "form": request.POST,
                "idempotency_token": idempotency_token or str(uuid.uuid4()),
            })

        description = note or ""
        idem_key = f"manual_settlement:{idempotency_token}"

        entry = TechnicianLedgerService.record_manual_settlement(
            company=company,
            technician=technician,
            amount_rial=amount_rial,
            direction=direction,
            reference=reference,
            description=description,
            created_by=request.user,
            idempotency_key=idem_key,
        )
        if entry is None:
            messages.warning(request, "این تسویه قبلاً ثبت شده است (تکراری).")
        messages.success(request, "تسویه با موفقیت ثبت شد.")
        return redirect(f"/{company.code}/admin/technicians/{technician.id}/ledger/")

    # GET: generate fresh idempotency token
    idempotency_token = str(uuid.uuid4())
    return render(request, "payouts/technician_settlement.html", {
        "company": company,
        "technician": technician,
        "balance": balance,
        "directions": _SETTLEMENT_DIRECTIONS,
        "errors": [],
        "form": {},
        "idempotency_token": idempotency_token,
    })
