"""
Invoices - Wage Calculation Service.

Calculates live technician wage previews for issued invoices. Phase 2 makes the
calculation policy-aware:
- row-level discounts are already baked into InvoiceItem.total_price;
- extra/manual invoice discounts and campaign discounts are allocated according
  to the company's financial policy;
- the returned wage is a preview until the invoice is settled at PAID time.
"""
from decimal import Decimal, ROUND_HALF_UP
import logging

from apps.tenants.models import CompanyFinancialPolicy

from .models import Invoice, InvoiceItem

logger = logging.getLogger(__name__)
MONEY = Decimal("1")


def _dec(value, default="0") -> Decimal:
    """Safely convert to Decimal."""
    if value is None:
        return Decimal(default)
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal(default)


def _money(value) -> Decimal:
    return _dec(value).quantize(MONEY, rounding=ROUND_HALF_UP)


def _get_wage_percentages(invoice: Invoice) -> tuple[Decimal, Decimal, Decimal]:
    """
    Get wage percentages for live preview calculation.

    Priority:
    1. Invoice snapshot fields if any is non-zero.
    2. Technician current fields only for DRAFT invoices with empty snapshots.
    3. Default: 0, 0, 0.
    """
    service_pct = _dec(invoice.technician_service_wage_percent_snapshot)
    goods_pct = _dec(invoice.technician_goods_wage_percent_snapshot)
    travel_pct = _dec(invoice.technician_travel_wage_percent_snapshot)

    if service_pct == 0 and goods_pct == 0 and travel_pct == 0:
        if invoice.status == Invoice.Status.DRAFT:
            technician = None
            order = getattr(invoice, "order", None)
            if order:
                technician = getattr(order, "technician", None)
            if technician:
                service_pct = _dec(getattr(technician, "service_wage_percent", 0))
                goods_pct = _dec(getattr(technician, "goods_wage_percent", 0))
                travel_pct = _dec(getattr(technician, "travel_wage_percent", 0))

    return service_pct, goods_pct, travel_pct


def _get_snapshot_wage_percentages(invoice: Invoice) -> tuple[Decimal, Decimal, Decimal]:
    """Return only invoice snapshot percentages; never fall back to live technician data."""
    return (
        _dec(invoice.technician_service_wage_percent_snapshot),
        _dec(invoice.technician_goods_wage_percent_snapshot),
        _dec(invoice.technician_travel_wage_percent_snapshot),
    )


def _collect_category_totals(invoice: Invoice) -> tuple[Decimal, Decimal, Decimal]:
    """Collect service/goods/travel totals from item.total_price after row discounts."""
    service_total = Decimal("0")
    goods_total = Decimal("0")
    travel_total = Decimal("0")

    for item in invoice.items.all():
        net = _dec(item.total_price)
        row_type = getattr(item, "row_type", "") or ""

        if row_type == InvoiceItem.RowType.TRAVEL:
            travel_total += net
        elif row_type == InvoiceItem.RowType.GOODS:
            goods_total += net
        elif row_type == InvoiceItem.RowType.SERVICE:
            service_total += net
        else:
            desc = (getattr(item, "description", "") or "").strip()
            if "ایاب" in desc or "ذهاب" in desc:
                logger.warning("InvoiceItem %s used legacy description fallback as travel", getattr(item, "id", None))
                travel_total += net
            elif desc == "تخفیف مازاد":
                logger.warning("InvoiceItem %s skipped legacy extra-discount pseudo-row", getattr(item, "id", None))
            else:
                logger.warning("InvoiceItem %s used legacy description fallback as service", getattr(item, "id", None))
                service_total += net

    return _money(service_total), _money(goods_total), _money(travel_total)


def _load_policy_strings(invoice: Invoice) -> tuple[str, str]:
    """Return (campaign_policy, extra_policy), creating defaults if needed."""
    policy, _ = CompanyFinancialPolicy.objects.get_or_create(
        company=invoice.company,
        defaults={
            "campaign_discount_policy": CompanyFinancialPolicy.DiscountPolicy.COMPANY,
            "extra_discount_policy": CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN,
        },
    )
    return policy.campaign_discount_policy, policy.extra_discount_policy


def _allocate_discount(
    *,
    discount: Decimal,
    policy: str,
    technician_gross_share: Decimal,
    company_gross_share: Decimal,
) -> tuple[Decimal, Decimal]:
    """Allocate one discount amount between technician and company."""
    discount = max(_money(discount), Decimal("0"))
    technician_gross_share = max(_money(technician_gross_share), Decimal("0"))
    company_gross_share = max(_money(company_gross_share), Decimal("0"))

    if discount <= 0:
        return Decimal("0"), Decimal("0")

    if policy == CompanyFinancialPolicy.DiscountPolicy.TECHNICIAN:
        return discount, Decimal("0")

    if policy == CompanyFinancialPolicy.DiscountPolicy.HALF_HALF:
        tech_absorbed = (discount / Decimal("2")).quantize(MONEY, rounding=ROUND_HALF_UP)
        return tech_absorbed, discount - tech_absorbed

    if policy == CompanyFinancialPolicy.DiscountPolicy.PROPORTIONAL_SHARE:
        total_gross = technician_gross_share + company_gross_share
        if total_gross <= 0:
            return Decimal("0"), discount
        tech_absorbed = (discount * technician_gross_share / total_gross).quantize(MONEY, rounding=ROUND_HALF_UP)
        return tech_absorbed, discount - tech_absorbed

    # Default and COMPANY policy: company absorbs the full discount.
    return Decimal("0"), discount


def _calculate_policy_aware_wage(
    *,
    invoice: Invoice,
    use_snapshot_percentages_only: bool = False,
    campaign_policy: str | None = None,
    extra_policy: str | None = None,
) -> dict:
    service_total, goods_total, travel_total = _collect_category_totals(invoice)

    if use_snapshot_percentages_only:
        service_pct, goods_pct, travel_pct = _get_snapshot_wage_percentages(invoice)
    else:
        service_pct, goods_pct, travel_pct = _get_wage_percentages(invoice)

    service_wage = _money(service_total * service_pct / Decimal("100"))
    goods_wage = _money(goods_total * goods_pct / Decimal("100"))
    travel_wage = _money(travel_total * travel_pct / Decimal("100"))
    technician_gross_share = _money(service_wage + goods_wage + travel_wage)

    invoice_net_total = _money(service_total + goods_total + travel_total)
    company_gross_share = max(_money(invoice_net_total - technician_gross_share), Decimal("0"))

    if campaign_policy is None or extra_policy is None:
        campaign_policy, extra_policy = _load_policy_strings(invoice)

    extra_discount = _money(getattr(invoice, "extra_discount_amount", 0))
    campaign_discount = _money(getattr(invoice, "campaign_discount_amount", 0))

    tech_extra_absorbed, comp_extra_absorbed = _allocate_discount(
        discount=extra_discount,
        policy=extra_policy,
        technician_gross_share=technician_gross_share,
        company_gross_share=company_gross_share,
    )
    tech_campaign_absorbed, comp_campaign_absorbed = _allocate_discount(
        discount=campaign_discount,
        policy=campaign_policy,
        technician_gross_share=technician_gross_share,
        company_gross_share=company_gross_share,
    )

    total_tech_absorbed = _money(tech_extra_absorbed + tech_campaign_absorbed)
    total_comp_absorbed = _money(comp_extra_absorbed + comp_campaign_absorbed)

    final_technician_wage = max(_money(technician_gross_share - total_tech_absorbed), Decimal("0"))
    final_company_share = max(_money(company_gross_share - total_comp_absorbed), Decimal("0"))

    return {
        "service_total": service_total,
        "goods_total": goods_total,
        "travel_total": travel_total,
        "extra_discount": extra_discount,
        "campaign_discount": campaign_discount,
        "service_base": service_total,  # transitional alias for existing templates
        "goods_base": goods_total,
        "travel_base": travel_total,
        "service_percent": service_pct,
        "goods_percent": goods_pct,
        "travel_percent": travel_pct,
        "service_wage": service_wage,
        "goods_wage": goods_wage,
        "travel_wage": travel_wage,
        "technician_gross_share": technician_gross_share,
        "company_gross_share": company_gross_share,
        "tech_extra_absorbed": tech_extra_absorbed,
        "comp_extra_absorbed": comp_extra_absorbed,
        "tech_campaign_absorbed": tech_campaign_absorbed,
        "comp_campaign_absorbed": comp_campaign_absorbed,
        "total_tech_absorbed": total_tech_absorbed,
        "total_comp_absorbed": total_comp_absorbed,
        "final_technician_wage": final_technician_wage,
        "final_company_share": final_company_share,
        "total_wage": final_technician_wage,  # backwards-compatible key
        "extra_discount_policy": extra_policy,
        "campaign_discount_policy": campaign_policy,
        "is_preview": getattr(invoice, "status", "") != Invoice.Status.PAID,
    }


def calculate_technician_wage(invoice: Invoice) -> dict:
    """Calculate a live policy-aware technician wage preview from invoice items."""
    return _calculate_policy_aware_wage(invoice=invoice, use_snapshot_percentages_only=False)


def snapshot_wage_percentages_on_invoice(invoice: Invoice) -> None:
    """
    Snapshot current technician wage percentages onto the invoice.

    Called during invoice issue. This snapshots only percentages; the final wage
    amount is locked later at PAID time by InvoiceSettlementService.
    """
    if (
        invoice.technician_service_wage_percent_snapshot != 0
        or invoice.technician_goods_wage_percent_snapshot != 0
        or invoice.technician_travel_wage_percent_snapshot != 0
    ):
        return

    technician = None
    order = getattr(invoice, "order", None)
    if order:
        technician = getattr(order, "technician", None)

    if technician is None:
        return

    invoice.technician_service_wage_percent_snapshot = _dec(
        getattr(technician, "service_wage_percent", 0)
    )
    invoice.technician_goods_wage_percent_snapshot = _dec(
        getattr(technician, "goods_wage_percent", 0)
    )
    invoice.technician_travel_wage_percent_snapshot = _dec(
        getattr(technician, "travel_wage_percent", 0)
    )
    invoice.save(update_fields=[
        "technician_service_wage_percent_snapshot",
        "technician_goods_wage_percent_snapshot",
        "technician_travel_wage_percent_snapshot",
        "updated_at",
    ])
