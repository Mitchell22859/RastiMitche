"""
Invoice settlement service.

Finalizes the financial result at the moment an invoice becomes PAID. This file
writes only settled_* snapshot fields and must be called inside the same
transaction as the PAID status transition.
"""
from decimal import Decimal

from django.utils import timezone

from apps.tenants.models import CompanyFinancialPolicy

from .models import Invoice
from .services_wage import _calculate_policy_aware_wage, _money


class InvoiceSettlementService:
    """Freeze policy-aware financial settlement on an invoice."""

    @staticmethod
    def settle(
        *,
        invoice: Invoice,
        payment_method: str = "",
        payment_reference: str = "",
        discount_code_id: int | None = None,
    ) -> Invoice:
        if invoice.settled_at is not None:
            raise ValueError("Invoice is already settled.")

        policy, _ = CompanyFinancialPolicy.objects.get_or_create(
            company=invoice.company,
            defaults={
                "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
                "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
            },
        )

        result = _run_settlement_calculation(invoice=invoice, policy=policy)

        invoice.settled_service_total = result["service_total"]
        invoice.settled_goods_total = result["goods_total"]
        invoice.settled_travel_total = result["travel_total"]
        invoice.settled_extra_discount_amount = result["extra_discount"]
        invoice.settled_campaign_discount_amount = result["campaign_discount"]
        invoice.settled_campaign_discount_policy = policy.campaign_discount_policy
        invoice.settled_extra_discount_policy = policy.extra_discount_policy
        invoice.settled_technician_gross_share = result["technician_gross_share"]
        invoice.settled_company_gross_share = result["company_gross_share"]
        invoice.settled_technician_absorbed_discount = result["total_tech_absorbed"]
        invoice.settled_company_absorbed_discount = result["total_comp_absorbed"]
        invoice.settled_technician_wage = result["final_technician_wage"]
        invoice.settled_company_share = result["final_company_share"]
        invoice.settled_payment_method = payment_method or ""
        invoice.settled_payment_reference = payment_reference or ""
        invoice.settled_discount_code_id = discount_code_id
        invoice.settled_at = timezone.now()

        invoice.save(update_fields=[
            "settled_service_total",
            "settled_goods_total",
            "settled_travel_total",
            "settled_extra_discount_amount",
            "settled_campaign_discount_amount",
            "settled_campaign_discount_policy",
            "settled_extra_discount_policy",
            "settled_technician_gross_share",
            "settled_company_gross_share",
            "settled_technician_absorbed_discount",
            "settled_company_absorbed_discount",
            "settled_technician_wage",
            "settled_company_share",
            "settled_payment_method",
            "settled_payment_reference",
            "settled_discount_code_id",
            "settled_at",
            "updated_at",
        ])
        return invoice


def _run_settlement_calculation(*, invoice: Invoice, policy: CompanyFinancialPolicy) -> dict:
    """Pure-ish calculation wrapper used by settlement; writes nothing."""
    result = _calculate_policy_aware_wage(
        invoice=invoice,
        use_snapshot_percentages_only=True,
        campaign_policy=policy.campaign_discount_policy,
        extra_policy=policy.extra_discount_policy,
    )

    # Keep a non-blocking sanity guard for future regressions.
    invoice_net_total = _money(
        result["service_total"] + result["goods_total"] + result["travel_total"]
    )
    split_total = _money(result["final_technician_wage"] + result["final_company_share"])
    if split_total > invoice_net_total:
        # Do not block customer payment; settlement values are floored and audited.
        import logging
        logging.getLogger(__name__).error(
            "Invoice settlement split exceeds invoice net total: invoice_id=%s split=%s net=%s",
            getattr(invoice, "id", None),
            split_total,
            invoice_net_total,
        )

    return result
