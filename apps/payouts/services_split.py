"""
Payouts - Split Decision Service.

Computes the payout routing decision for a payment without touching any gateway.
This is a pure calculation service; no DB writes except the optional snapshot.
"""
from __future__ import annotations

import logging
from decimal import Decimal, ROUND_DOWN

logger = logging.getLogger(__name__)

_ONLINE_GATEWAY_TYPES = {"zarinpal", "idpay", "nextpay", "fake"}


class PaymentSplitDecisionService:
    """
    Determines how the money from a paid invoice should be routed.

    Balance convention mirrors TechnicianLedgerService:
      technician_direct_amount  → technician receives this via PSP split (P4+)
      technician_ledger_amount  → company owes technician this as internal ledger credit
      company_deposit_amount    → company keeps this after fees
    """

    @staticmethod
    def compute(invoice, payment=None) -> dict:
        """
        Compute the split decision for a paid (or about-to-be-paid) invoice.

        Returns a dict with all split amounts and the reasoning.
        Does NOT write anything to the database.
        """
        from apps.tenants.models import CompanyFinancialPolicy
        from apps.payouts.services import _get_technician_for_invoice

        technician = _get_technician_for_invoice(invoice)
        total_amount = int(invoice.total_amount or 0)
        tech_wage = int(invoice.settled_technician_wage or 0)

        # Load financial policy (get_or_create to handle missing policy gracefully)
        policy, _ = CompanyFinancialPolicy.objects.get_or_create(
            company=invoice.company,
            defaults={
                "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
                "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
                "payout_strategy": CompanyFinancialPolicy.PayoutStrategy.DIRECT_TO_COMPANY,
                "platform_fee_percent": Decimal("0"),
            },
        )

        payout_strategy = policy.payout_strategy
        platform_fee_percent = Decimal(str(policy.platform_fee_percent or "0"))
        platform_fee_amount = int(
            (Decimal(total_amount) * platform_fee_percent / Decimal("100"))
            .to_integral_value(rounding=ROUND_DOWN)
        )

        # Technician verification snapshot
        tech_verified = False
        tech_sub_merchant_id = ""
        if technician is not None:
            tech_verified = bool(technician.shaba_verified)
            tech_sub_merchant_id = technician.sub_merchant_id or ""

        # Split decision
        can_split = (
            payout_strategy == CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN
            and tech_verified
            and bool(tech_sub_merchant_id)
            and tech_wage > 0
        )

        if can_split:
            technician_direct_amount = tech_wage
            technician_ledger_amount = 0
            company_deposit_amount = max(0, total_amount - platform_fee_amount - technician_direct_amount)
            reason = "split_with_verified_technician"
        else:
            technician_direct_amount = 0
            technician_ledger_amount = tech_wage
            company_deposit_amount = max(0, total_amount - platform_fee_amount)
            if payout_strategy != CompanyFinancialPolicy.PayoutStrategy.SPLIT_WITH_TECHNICIAN:
                reason = "payout_strategy_is_direct_to_company"
            elif not tech_verified:
                reason = "technician_not_verified"
            elif not tech_sub_merchant_id:
                reason = "technician_has_no_sub_merchant_id"
            elif tech_wage <= 0:
                reason = "technician_wage_is_zero"
            else:
                reason = "fallback_to_company"

        return {
            "should_split_with_technician": can_split,
            "reason": reason,
            "total_amount": total_amount,
            "platform_fee_percent": float(platform_fee_percent),
            "platform_fee_amount": platform_fee_amount,
            "company_deposit_amount": company_deposit_amount,
            "technician_direct_amount": technician_direct_amount,
            "technician_ledger_amount": technician_ledger_amount,
            "technician_share_amount": tech_wage,
            "payout_strategy_snapshot": payout_strategy,
            "technician_verified_snapshot": tech_verified,
            "technician_sub_merchant_id_snapshot": tech_sub_merchant_id,
            "platform_fee_percent_snapshot": float(platform_fee_percent),
        }

    @staticmethod
    def create_snapshot(payment, invoice) -> "PaymentSplitSnapshot | None":
        """
        Compute the split decision and persist a PaymentSplitSnapshot row.

        Idempotent: if a snapshot already exists for this payment, returns it.
        Safe to call inside the payment verify transaction.
        """
        from .models import PaymentSplitSnapshot

        existing = PaymentSplitSnapshot.objects.filter(payment=payment).first()
        if existing is not None:
            return existing

        try:
            decision = PaymentSplitDecisionService.compute(invoice, payment)
        except Exception:
            logger.exception(
                "PaymentSplitDecisionService.compute failed for payment %s",
                getattr(payment, "id", None),
            )
            return None

        try:
            return PaymentSplitSnapshot.objects.create(
                company=payment.company,
                payment=payment,
                invoice=invoice,
                total_amount=decision["total_amount"],
                platform_fee_amount=decision["platform_fee_amount"],
                company_deposit_amount=decision["company_deposit_amount"],
                technician_direct_amount=decision["technician_direct_amount"],
                technician_ledger_amount=decision["technician_ledger_amount"],
                payout_strategy_snapshot=decision["payout_strategy_snapshot"],
                technician_verified_snapshot=decision["technician_verified_snapshot"],
                technician_sub_merchant_id_snapshot=decision["technician_sub_merchant_id_snapshot"],
                platform_fee_percent_snapshot=Decimal(str(decision["platform_fee_percent_snapshot"])),
                should_split_with_technician=decision["should_split_with_technician"],
                reason=decision["reason"],
                raw_decision=decision,
            )
        except Exception:
            logger.exception(
                "Failed to save PaymentSplitSnapshot for payment %s",
                getattr(payment, "id", None),
            )
            return None
