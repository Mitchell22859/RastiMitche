"""
Platform Core - Split Snapshot Views (Platform Owner).

Cross-company report of all PaymentSplitSnapshot rows.
"""
import json

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import render

from apps.accounts.permissions import require_platform_owner
from apps.payouts.models import PaymentSplitSnapshot
from apps.payouts.views_split_snapshots import REASON_LABELS
from apps.tenants.models import Company


def _base_qs():
    return (
        PaymentSplitSnapshot.objects
        .select_related(
            "company",
            "payment",
            "payment__gateway",
            "invoice",
            "invoice__order",
            "invoice__order__technician",
            "invoice__order__technician__user",
        )
        .order_by("-created_at", "-id")
    )


@require_platform_owner
def split_snapshot_list(request: HttpRequest) -> HttpResponse:
    qs = _base_qs()

    company_filter = request.GET.get("company", "")
    split_filter = request.GET.get("split", "")
    reason_filter = request.GET.get("reason", "")
    q = request.GET.get("q", "").strip()

    if company_filter:
        qs = qs.filter(company_id=company_filter)

    if split_filter == "yes":
        qs = qs.filter(should_split_with_technician=True)
    elif split_filter == "no":
        qs = qs.filter(should_split_with_technician=False)

    if reason_filter:
        qs = qs.filter(reason=reason_filter)

    if q:
        qs = qs.filter(invoice__invoice_number__icontains=q) | \
             qs.filter(payment__tracking_code__icontains=q) | \
             qs.filter(payment__reference_id__icontains=q)
        qs = qs.distinct()

    companies = Company.objects.filter(is_active=True).order_by("name")
    reason_choices = list(REASON_LABELS.items())

    return render(request, "platform_core/split_snapshot_list.html", {
        "snapshots": qs[:500],
        "companies": companies,
        "company_filter": company_filter,
        "split_filter": split_filter,
        "reason_filter": reason_filter,
        "q": q,
        "reason_choices": reason_choices,
    })


@require_platform_owner
def split_snapshot_detail(request: HttpRequest, snapshot_id: int) -> HttpResponse:
    try:
        snapshot = _base_qs().get(id=snapshot_id)
    except PaymentSplitSnapshot.DoesNotExist:
        raise Http404("اسنپ‌شات یافت نشد.")

    reason_label = REASON_LABELS.get(snapshot.reason, "دلیل نامشخص/نیازمند بررسی.")
    raw_json = json.dumps(snapshot.raw_decision, ensure_ascii=False, indent=2)

    return render(request, "platform_core/split_snapshot_detail.html", {
        "snapshot": snapshot,
        "reason_label": reason_label,
        "raw_json": raw_json,
    })
