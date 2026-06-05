"""
Platform Core - Technician Financial Verification Views.

Platform-owner-only pages for reviewing and approving/rejecting
technician SHABA verification requests.
"""
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone

from apps.accounts.models import Technician
from apps.accounts.permissions import require_platform_owner
from apps.tenants.models import Company


@require_platform_owner
def verification_list(request: HttpRequest) -> HttpResponse:
    """List technicians with financial verification state, with filters."""
    status_filter = request.GET.get("status", "")
    company_filter = request.GET.get("company", "")
    search = request.GET.get("q", "").strip()

    qs = Technician.objects.select_related("user", "company").order_by(
        "-verification_updated_at", "-id"
    )

    if status_filter:
        qs = qs.filter(financial_verification_status=status_filter)
    if company_filter:
        qs = qs.filter(company_id=company_filter)
    if search:
        qs = qs.filter(
            user__first_name__icontains=search
        ) | qs.filter(
            user__last_name__icontains=search
        ) | qs.filter(
            user__username__icontains=search
        ) | qs.filter(
            user__phone__icontains=search
        ) | qs.filter(
            shaba_number__icontains=search
        )

    # De-duplicate after OR filter
    qs = qs.distinct()

    companies = Company.objects.filter(is_active=True).order_by("name")
    status_choices = Technician.FinancialVerificationStatus.choices

    return render(request, "platform_core/technician_verification_list.html", {
        "technicians": qs,
        "companies": companies,
        "status_choices": status_choices,
        "status_filter": status_filter,
        "company_filter": company_filter,
        "search": search,
    })


@require_platform_owner
def verification_detail(request: HttpRequest, technician_id: int) -> HttpResponse:
    """Review and approve/reject a technician's financial verification."""
    try:
        technician = Technician.objects.select_related("user", "company").get(
            id=technician_id
        )
    except Technician.DoesNotExist:
        raise Http404("تکنسین یافت نشد.")

    error = ""
    success = ""

    if request.method == "POST":
        action = request.POST.get("action", "")

        if action == "approve":
            sub_merchant_id = request.POST.get("sub_merchant_id", "").strip()
            note = request.POST.get("verification_note", "").strip()

            technician.financial_verification_status = (
                Technician.FinancialVerificationStatus.VERIFIED
            )
            technician.shaba_verified = True
            technician.shaba_verified_at = timezone.now()
            technician.verified_by = request.user
            technician.rejected_by = None
            technician.verification_note = note
            technician.verification_updated_at = timezone.now()
            if sub_merchant_id:
                technician.sub_merchant_id = sub_merchant_id
            technician.save(update_fields=[
                "financial_verification_status",
                "shaba_verified",
                "shaba_verified_at",
                "verified_by",
                "rejected_by",
                "verification_note",
                "verification_updated_at",
                "sub_merchant_id",
            ])
            success = "تأیید شبا با موفقیت انجام شد."

        elif action == "reject":
            note = request.POST.get("verification_note", "").strip()
            if not note:
                error = "برای رد درخواست، وارد کردن دلیل الزامی است."
            else:
                technician.financial_verification_status = (
                    Technician.FinancialVerificationStatus.REJECTED
                )
                technician.shaba_verified = False
                technician.shaba_verified_at = None
                technician.rejected_by = request.user
                technician.verified_by = None
                technician.verification_note = note
                technician.verification_updated_at = timezone.now()
                technician.save(update_fields=[
                    "financial_verification_status",
                    "shaba_verified",
                    "shaba_verified_at",
                    "rejected_by",
                    "verified_by",
                    "verification_note",
                    "verification_updated_at",
                ])
                success = "درخواست رد شد."

        elif action == "set_sub_merchant":
            sub_merchant_id = request.POST.get("sub_merchant_id", "").strip()
            technician.sub_merchant_id = sub_merchant_id
            technician.save(update_fields=["sub_merchant_id"])
            success = "شناسه پذیرنده فرعی ذخیره شد."

        elif action == "clear":
            technician.financial_verification_status = (
                Technician.FinancialVerificationStatus.NOT_SUBMITTED
            )
            technician.shaba_verified = False
            technician.shaba_verified_at = None
            technician.verified_by = None
            technician.rejected_by = None
            technician.verification_note = ""
            technician.verification_updated_at = timezone.now()
            technician.save(update_fields=[
                "financial_verification_status",
                "shaba_verified",
                "shaba_verified_at",
                "verified_by",
                "rejected_by",
                "verification_note",
                "verification_updated_at",
            ])
            success = "وضعیت تأیید بازنشانی شد."
        else:
            error = "عملیات نامعتبر."

        if success and not error:
            return redirect(
                f"/owner-platform/technician-financial-verifications/{technician_id}/"
                f"?success={success}"
            )

    success = request.GET.get("success", success)

    return render(request, "platform_core/technician_verification_detail.html", {
        "technician": technician,
        "error": error,
        "success": success,
    })
