"""
Platform owner management of per-company password reset SMS billing policy.
URL prefix: /owner-platform/password-reset-policy/
"""
from __future__ import annotations

from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.models import PasswordResetSMSBillingPolicy, UserRole
from apps.accounts.permissions import require_platform_owner
from apps.tenants.models import Company


_PAYER_CHOICES = PasswordResetSMSBillingPolicy.Payer.choices

_FIELD_LABELS = {
    "company_admin_payer": "مدیر شرکت",
    "operator_payer": "اپراتور",
    "technician_payer": "نیروی خدماتی",
    "customer_payer": "مشتری",
}

_PAYER_FIELDS = list(_FIELD_LABELS.keys())


@require_platform_owner
def policy_list(request: HttpRequest) -> HttpResponse:
    """List all companies with their current billing policy."""
    companies = Company.objects.all().order_by("name")
    policy_map = {
        p.company_id: p
        for p in PasswordResetSMSBillingPolicy.objects.select_related("company").all()
    }

    rows = []
    for company in companies:
        policy = policy_map.get(company.pk)
        rows.append({
            "company": company,
            "policy": policy,
            "has_policy": policy is not None,
            "any_company_paid": policy and any(
                getattr(policy, f) == PasswordResetSMSBillingPolicy.Payer.COMPANY
                for f in _PAYER_FIELDS
            ),
        })

    return render(request, "platform_core/password_reset_policy/list.html", {
        "rows": rows,
        "default_label": "مالک پلتفرم (پیش‌فرض)",
    })


@require_platform_owner
def policy_edit(request: HttpRequest, company_id: int) -> HttpResponse:
    """Create or update a company's billing policy."""
    company = Company.objects.filter(pk=company_id).first()
    if not company:
        raise Http404("شرکت یافت نشد.")

    policy, _ = PasswordResetSMSBillingPolicy.objects.get_or_create(
        company=company,
        defaults={f: PasswordResetSMSBillingPolicy.Payer.PLATFORM for f in _PAYER_FIELDS},
    )

    error = ""
    success = ""

    if request.method == "POST":
        valid = True
        new_values = {}
        for field in _PAYER_FIELDS:
            val = request.POST.get(field, "").strip()
            if val not in dict(_PAYER_CHOICES):
                valid = False
                error = f"مقدار نامعتبر برای فیلد {_FIELD_LABELS[field]}."
                break
            new_values[field] = val

        if valid:
            for field, val in new_values.items():
                setattr(policy, field, val)
            policy.updated_by = request.user
            policy.save()
            success = "سیاست پرداخت ذخیره شد."

    field_rows = [
        {
            "field": f,
            "label": _FIELD_LABELS[f],
            "value": getattr(policy, f),
        }
        for f in _PAYER_FIELDS
    ]

    return render(request, "platform_core/password_reset_policy/edit.html", {
        "company": company,
        "policy": policy,
        "field_rows": field_rows,
        "payer_choices": _PAYER_CHOICES,
        "error": error,
        "success": success,
    })
