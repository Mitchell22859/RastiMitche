"""
Invoice Financial Preview Service (Payment P6).

Pure read — never writes to DB. Returns a breakdown of how an invoice
would be settled if marked paid right now.

Uses the same wage calculation logic as settlement to ensure consistency.
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
          technician_wage_percent Decimal — effective average wage percent
          technician_wage_amount  int  — rial
          company_net_amount    int  — total - platform_fee - technician_wage
          payout_strategy       str  — from policy or ""
          technician_name       str  — display name or ""
          is_paid               bool
          already_has_fee_entry bool — True if platform fee already recorded
        """
        from apps.payouts.services_platform_fee import _get_policy_fee_percent
        from apps.invoices.models import Invoice

        total = int(invoice.total_amount or 0)
        is_paid = invoice.status == Invoice.Status.PAID

        # --- Platform fee ---
        fee_pct = _get_policy_fee_percent(invoice.company)
        fee_amount = int(Decimal(str(total)) * fee_pct / 100) if fee_pct else 0

        # --- Technician wage ---
        # For paid invoices, use the frozen settled values.
        # For unpaid invoices, use the same calculation as settlement.
        tech_wage_amount = 0
        tech_wage_pct = Decimal("0")

        if is_paid and invoice.settled_technician_wage is not None:
            tech_wage_amount = int(invoice.settled_technician_wage)
            # Compute effective percent for display
            if total > 0 and tech_wage_amount > 0:
                tech_wage_pct = (Decimal(str(tech_wage_amount)) * 100 / Decimal(str(total))).quantize(Decimal("0.01"))
        else:
            # Use the same policy-aware calculation as settlement
            try:
                from apps.invoices.services_wage import _calculate_policy_aware_wage
                wage_result = _calculate_policy_aware_wage(
                    invoice=invoice,
                    use_snapshot_percentages_only=False,
                )
                tech_wage_amount = int(wage_result.get("final_technician_wage", 0))
                if total > 0 and tech_wage_amount > 0:
                    tech_wage_pct = (Decimal(str(tech_wage_amount)) * 100 / Decimal(str(total))).quantize(Decimal("0.01"))
            except Exception:
                pass

        # --- Payout strategy ---
        payout_strategy = ""
        try:
            from apps.tenants.models import CompanyFinancialPolicy
            policy = CompanyFinancialPolicy.objects.filter(company=invoice.company).first()
            if policy:
                payout_strategy = getattr(policy, "payout_strategy", "") or ""
        except Exception:
            pass

        # --- Technician name ---
        technician_name = ""
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

        # --- Check if fee entry already exists ---
        already_has_fee_entry = False
        try:
            from apps.payouts.models import CompanyPlatformFeeEntry
            already_has_fee_entry = CompanyPlatformFeeEntry.objects.filter(
                idempotency_key=f"platform_fee:invoice:{invoice.id}"
            ).exists()
        except Exception:
            pass

        company_net = total - fee_amount - tech_wage_amount

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
