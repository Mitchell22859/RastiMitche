"""
Payouts - Views.

Read-only technician ledger page for company admins.
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render

from apps.accounts.models import Technician
from apps.common.permissions import require_role, require_tenant

from .services import TechnicianLedgerService


@login_required
@require_tenant
@require_role("COMPANY_ADMIN", "COMPANY_STAFF")
def technician_ledger(request, technician_id: int, company_code=None):
    company = request.company
    technician = get_object_or_404(
        Technician, id=technician_id, company=company
    )

    balance = TechnicianLedgerService.get_balance(company, technician)
    entries = TechnicianLedgerService.list_statement(company, technician)

    return render(
        request,
        "payouts/technician_ledger.html",
        {
            "company": company,
            "technician": technician,
            "balance": balance,
            "entries": entries,
        },
    )


