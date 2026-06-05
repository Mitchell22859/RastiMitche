"""
Invoice Financial Preview Service (Payment P6).

Pure read — never writes to DB. Returns a breakdown of how an invoice
would be settled if marked paid right now.
"""
from __future__ import annotations

from decimal import Decimal


class InvoiceFinancialPreviewService:
    """Compute financial breakdown for an invoice without any DB mutation."""

    @staticmethod
    def compute(invoice) -> dict:
        """
        Return a dict with all financial fields for the given invoice.

        Keys:
          total_amount          int  — invoice total (rial)
          platform_fee_percent  Decimal — fee % from policy (0 if none)
          platform_fee_amount   int  — computed fee (rial, floored)
          technician_wage_percent Decimal — from settled_* or snapshot
          technician_wage_amount  int  — rial
          company_net_amount    int  — total - platform_fee - technician_wage
          payout_strategy       str  — from policy or ""
          technician_name       str  — display name or ""
          is_paid               bool
          already_has_fee_entry bool — True if platform fee already recorded
        """
        from decimal import Decimal
        from apps.payouts.services_platform_fee import PlatformFeeService, _get_policy_fee_percent

        total = int(invoice.total_amount or 0)

        fee_pct = _get_policy_fee_percent(invoice.company)
        fee_amount = int(Decimal(str(total)) * fee_pct / 100) if fee_pct else 0

        # Technician wage
        tech_wage_pct = Decimal("0")
        tech_wage_amount = 0
        technician_name = ""

        # Try settled snapshot first (already paid), fall back to live policy
        if getattr(invoice, "settled_technician_wage_percent", None):
            tech_wage_pct = Decimal(str(invoice.settled_technician_wage_percent))
        else:
            try:
                from apps.tenants.models import CompanyFinancialPolicy
                policy = CompanyFinancialPolicy.objects.filter(company=invoice.company).first()
                if policy and policy.technician_wage_percent:
                    tech_wage_pct = Decimal(str(policy.technician_wage_percent))
            except Exception:
                pass

        tech_wage_amount = int(Decimal(str(total)) * tech_wage_pct / 100) if tech_wage_pct else 0

        # Payout strategy
        payout_strategy = ""
        try:
            from apps.tenants.models import CompanyFinancialPolicy
            policy = CompanyFinancialPolicy.objects.filter(company=invoice.company).first()
            if policy:
                payout_strategy = getattr(policy, "payout_strategy", "") or ""
        except Exception:
            pass

        # Technician from order
        try:
            order = getattr(invoice, "order", None)
            tech = getattr(order, "technician", None) if order else None
            if tech:
                user = getattr(tech, "user", None)
                if user:
                    technician_name = (
                        getattr(user, "get_full_name", lambda: "")()
                        or getattr(user, "username", "")
                    )
        except Exception:
            pass

        # Check if fee entry already exists
        already_has_fee_entry = False
        try:
            from apps.payouts.models import CompanyPlatformFeeEntry
            already_has_fee_entry = CompanyPlatformFeeEntry.objects.filter(
                idempotency_key=f"platform_fee:invoice:{invoice.id}"
            ).exists()
        except Exception:
            pass

        company_net = total - fee_amount - tech_wage_amount

        from apps.invoices.models import Invoice
        is_paid = invoice.status == Invoice.Status.PAID

        return {
            "total_amount": total,
            "platform_fee_percent": fee_pct,
            "platform_fee_amount": fee_amount,
            "technician_wage_percent": tech_wage_pct,
            "technician_wage_amount": tech_wage_amount,
            "company_net_amount": company_net,
            "payout_strategy": payout_strategy,
            "technician_name": technician_name,
            "is_paid": is_paid,
            "already_has_fee_entry": already_has_fee_entry,
        }
