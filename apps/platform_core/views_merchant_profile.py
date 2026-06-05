"""
Platform Core - Merchant/KYC Profile Review Views (Payment P5).

Platform owner pages for reviewing, approving, and rejecting company
merchant profiles and edit requests.
"""
import os

from django.http import Http404, HttpRequest, HttpResponse, FileResponse
from django.shortcuts import redirect, render

from apps.accounts.permissions import require_platform_owner
from apps.tenants.models import (
    Company,
    CompanyMerchantProfile,
    CompanyMerchantProfileChangeRequest,
)
from apps.tenants.services_merchant_profile import (
    MerchantProfileService,
    MerchantProfileChangeRequestService,
)

_DOCUMENT_FIELDS = ("national_card_image", "business_license_image", "latest_official_newspaper_image")
_DOCUMENT_LABELS = {
    "national_card_image": "کارت ملی",
    "business_license_image": "جواز کسب",
    "latest_official_newspaper_image": "آگهی روزنامه رسمی",
}


@require_platform_owner
def merchant_profile_list(request: HttpRequest) -> HttpResponse:
    qs = (
        CompanyMerchantProfile.objects
        .select_related("company", "reviewed_by")
        .order_by("-submitted_at", "-created_at")
    )

    status_filter = request.GET.get("status", "")
    company_filter = request.GET.get("company", "")
    q = request.GET.get("q", "").strip()

    if status_filter:
        qs = qs.filter(status=status_filter)
    if company_filter:
        qs = qs.filter(company_id=company_filter)
    if q:
        qs = qs.filter(company__name__icontains=q) | \
             qs.filter(company__code__icontains=q) | \
             qs.filter(owner_mobile__icontains=q) | \
             qs.filter(legal_company_name__icontains=q)
        qs = qs.distinct()

    companies = Company.objects.filter(is_active=True).order_by("name")
    status_choices = CompanyMerchantProfile.Status.choices

    return render(request, "platform_core/merchant_profile_list.html", {
        "profiles": qs[:300],
        "companies": companies,
        "status_choices": status_choices,
        "status_filter": status_filter,
        "company_filter": company_filter,
        "q": q,
    })


@require_platform_owner
def merchant_profile_detail(request: HttpRequest, profile_id: int) -> HttpResponse:
    try:
        profile = CompanyMerchantProfile.objects.select_related(
            "company", "reviewed_by"
        ).get(id=profile_id)
    except CompanyMerchantProfile.DoesNotExist:
        raise Http404("پروفایل یافت نشد.")

    error = ""
    success = request.GET.get("success", "")

    if request.method == "POST":
        action = request.POST.get("action", "")
        note = request.POST.get("review_note", "").strip()
        reason = request.POST.get("rejected_reason", "").strip()

        if action == "approve":
            MerchantProfileService.approve(profile, request.user, note)
            return redirect(f"/owner-platform/merchant-profiles/{profile_id}/?success=تأیید انجام شد.")
        elif action == "reject":
            if not reason:
                error = "دلیل رد الزامی است."
            else:
                MerchantProfileService.reject(profile, request.user, reason)
                return redirect(f"/owner-platform/merchant-profiles/{profile_id}/?success=پروفایل رد شد.")
        elif action == "under_review":
            MerchantProfileService.set_under_review(profile, request.user)
            return redirect(f"/owner-platform/merchant-profiles/{profile_id}/?success=وضعیت به «در حال بررسی» تغییر یافت.")
        elif action == "request_changes":
            if not note:
                error = "متن درخواست تغییر الزامی است."
            else:
                MerchantProfileService.request_changes(profile, request.user, note)
                return redirect(f"/owner-platform/merchant-profiles/{profile_id}/?success=درخواست تغییر ارسال شد.")
        else:
            error = "عملیات نامعتبر."

    return render(request, "platform_core/merchant_profile_detail.html", {
        "profile": profile,
        "error": error,
        "success": success,
        "document_fields": [
            (f, _DOCUMENT_LABELS.get(f, f), getattr(profile, f, None))
            for f in _DOCUMENT_FIELDS
        ],
    })


@require_platform_owner
def serve_profile_document(request: HttpRequest, profile_id: int, field_name: str) -> HttpResponse:
    """Serve a KYC document for platform owner review."""
    if field_name not in _DOCUMENT_FIELDS:
        raise Http404("Document not found.")
    try:
        profile = CompanyMerchantProfile.objects.get(id=profile_id)
    except CompanyMerchantProfile.DoesNotExist:
        raise Http404("پروفایل یافت نشد.")

    file_obj = getattr(profile, field_name, None)
    if not file_obj:
        raise Http404("Document not found.")
    try:
        return FileResponse(file_obj.open("rb"), as_attachment=False,
                            filename=os.path.basename(file_obj.name))
    except FileNotFoundError:
        raise Http404("Document file missing.")


@require_platform_owner
def serve_change_request_document(request: HttpRequest, request_id: int, field_name: str) -> HttpResponse:
    """Serve a KYC document from a change request for platform owner review."""
    if field_name not in _DOCUMENT_FIELDS:
        raise Http404("Document not found.")
    try:
        change_req = CompanyMerchantProfileChangeRequest.objects.get(id=request_id)
    except CompanyMerchantProfileChangeRequest.DoesNotExist:
        raise Http404("درخواست یافت نشد.")

    file_obj = getattr(change_req, field_name, None)
    if not file_obj:
        raise Http404("Document not found.")
    try:
        return FileResponse(file_obj.open("rb"), as_attachment=False,
                            filename=os.path.basename(file_obj.name))
    except FileNotFoundError:
        raise Http404("Document file missing.")


@require_platform_owner
def change_request_list(request: HttpRequest) -> HttpResponse:
    qs = (
        CompanyMerchantProfileChangeRequest.objects
        .select_related("company", "profile", "created_by", "reviewed_by")
        .order_by("-created_at")
    )

    status_filter = request.GET.get("status", "")
    company_filter = request.GET.get("company", "")

    if status_filter:
        qs = qs.filter(status=status_filter)
    if company_filter:
        qs = qs.filter(company_id=company_filter)

    companies = Company.objects.filter(is_active=True).order_by("name")
    status_choices = CompanyMerchantProfileChangeRequest.Status.choices

    return render(request, "platform_core/merchant_profile_change_request_list.html", {
        "requests": qs[:300],
        "companies": companies,
        "status_choices": status_choices,
        "status_filter": status_filter,
        "company_filter": company_filter,
    })


@require_platform_owner
def change_request_detail(request: HttpRequest, request_id: int) -> HttpResponse:
    try:
        change_req = CompanyMerchantProfileChangeRequest.objects.select_related(
            "company", "profile", "created_by", "reviewed_by"
        ).get(id=request_id)
    except CompanyMerchantProfileChangeRequest.DoesNotExist:
        raise Http404("درخواست یافت نشد.")

    error = ""
    success = request.GET.get("success", "")

    if request.method == "POST":
        action = request.POST.get("action", "")
        note = request.POST.get("review_note", "").strip()

        if action == "approve":
            MerchantProfileChangeRequestService.approve(change_req, request.user, note)
            return redirect(f"/owner-platform/merchant-profile-change-requests/{request_id}/?success=تغییرات تأیید و اعمال شدند.")
        elif action == "reject":
            if not note:
                error = "دلیل رد الزامی است."
            else:
                MerchantProfileChangeRequestService.reject(change_req, request.user, note)
                return redirect(f"/owner-platform/merchant-profile-change-requests/{request_id}/?success=درخواست رد شد.")
        else:
            error = "عملیات نامعتبر."

    # Build diff view: current profile vs proposed changes
    from apps.tenants.services_merchant_profile import PROFILE_TEXT_FIELDS
    profile = change_req.profile
    diff_rows = []
    for field in PROFILE_TEXT_FIELDS:
        current = getattr(profile, field, "") or ""
        proposed = change_req.proposed_changes.get(field, "") or ""
        if current != proposed:
            diff_rows.append((field, current, proposed))

    return render(request, "platform_core/merchant_profile_change_request_detail.html", {
        "change_req": change_req,
        "diff_rows": diff_rows,
        "error": error,
        "success": success,
        "document_fields": [
            (f, _DOCUMENT_LABELS.get(f, f), getattr(change_req, f, None))
            for f in _DOCUMENT_FIELDS
        ],
    })
