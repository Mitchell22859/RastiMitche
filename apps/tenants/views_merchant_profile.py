"""
Tenants - Company Admin Merchant/KYC Profile Views (Payment P5).

Company admin pages for submitting and viewing KYC/banking information.
"""
import os

from django.contrib import messages as django_messages
from django.http import Http404, HttpRequest, HttpResponse, FileResponse
from django.shortcuts import redirect, render

from apps.accounts.permissions import require_tenant_role
from apps.common.permissions import require_tenant

from .models import CompanyMerchantProfile, CompanyMerchantProfileChangeRequest
from .services_merchant_profile import (
    MerchantProfileService,
    MerchantProfileChangeRequestService,
    PROFILE_TEXT_FIELDS,
)

_DOCUMENT_FIELDS = ("national_card_image", "business_license_image", "latest_official_newspaper_image")


@require_tenant
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def merchant_profile_view(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    profile = MerchantProfileService.get_or_create(company)
    errors = []
    success = ""

    if request.method == "POST" and profile.is_editable:
        errors = MerchantProfileService.submit(
            profile, request.user, request.POST, request.FILES
        )
        if not errors:
            success = "اطلاعات با موفقیت ارسال شد و در انتظار بررسی است."
            return redirect(f"/{company.code}/admin/payment/merchant-profile/?ok=1")

    ok = request.GET.get("ok")
    if ok:
        success = "اطلاعات با موفقیت ارسال شد."

    # Pending change requests
    pending_requests = CompanyMerchantProfileChangeRequest.objects.filter(
        company=company,
        status=CompanyMerchantProfileChangeRequest.Status.PENDING,
    )

    return render(request, "tenants/merchant_profile.html", {
        "company": company,
        "profile": profile,
        "errors": errors,
        "success": success,
        "pending_requests": pending_requests,
    })


@require_tenant
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def merchant_profile_edit_request_view(request: HttpRequest, **kwargs) -> HttpResponse:
    company = request.company
    profile = MerchantProfileService.get_or_create(company)

    if profile.status != CompanyMerchantProfile.Status.APPROVED:
        return redirect(f"/{company.code}/admin/payment/merchant-profile/")

    errors = []
    success = ""

    if request.method == "POST":
        change_req, errors = MerchantProfileChangeRequestService.submit(
            profile, request.user, request.POST, request.FILES
        )
        if not errors:
            return redirect(f"/{company.code}/admin/payment/merchant-profile/?ok=1")

    return render(request, "tenants/merchant_profile_edit_request.html", {
        "company": company,
        "profile": profile,
        "errors": errors,
        "success": success,
        "text_fields": PROFILE_TEXT_FIELDS,
    })


@require_tenant
@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def serve_profile_document(request: HttpRequest, field_name: str, **kwargs) -> HttpResponse:
    """Serve a KYC document file securely to the owning company's admin."""
    company = request.company
    profile = MerchantProfileService.get_or_create(company)

    if field_name not in _DOCUMENT_FIELDS:
        raise Http404("Document not found.")

    file_obj = getattr(profile, field_name, None)
    if not file_obj:
        raise Http404("Document not found.")

    try:
        return FileResponse(file_obj.open("rb"), as_attachment=False,
                            filename=os.path.basename(file_obj.name))
    except FileNotFoundError:
        raise Http404("Document file missing.")
