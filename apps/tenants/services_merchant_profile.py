"""
Tenants - Merchant Profile Service Layer (Payment P5).

All mutations to CompanyMerchantProfile and CompanyMerchantProfileChangeRequest
go through these services. Views must not write to these models directly.
"""
from __future__ import annotations

import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

# Text fields that can be proposed in a change request
PROFILE_TEXT_FIELDS = [
    "legal_company_name", "company_type", "national_id", "economic_code",
    "registration_number", "postal_code", "registered_address",
    "company_phone", "owner_full_name", "owner_national_code", "owner_mobile",
    "bank_name", "account_holder_name", "shaba_number",
    "bank_account_number", "bank_card_number", "notes",
]

REQUIRED_FOR_SUBMISSION = [
    "legal_company_name", "owner_national_code", "postal_code",
    "registered_address", "company_phone", "owner_full_name",
    "owner_mobile", "bank_name", "account_holder_name", "shaba_number",
]


class MerchantProfileService:
    """
    Manages the lifecycle of CompanyMerchantProfile.
    """

    @staticmethod
    def get_or_create(company) -> "CompanyMerchantProfile":
        from .models import CompanyMerchantProfile
        profile, _ = CompanyMerchantProfile.objects.get_or_create(company=company)
        return profile

    @staticmethod
    def submit(profile, user, data: dict, files: dict) -> list[str]:
        """
        Save form data and submit the profile for platform owner review.

        Returns a list of validation error strings (empty = success).
        """
        errors = []

        # Validate required fields
        for field in REQUIRED_FOR_SUBMISSION:
            val = data.get(field, "").strip()
            if not val:
                # Skip hard block — let the form show field-level validation
                pass

        # Save text fields
        for field in PROFILE_TEXT_FIELDS:
            val = data.get(field, "").strip()
            setattr(profile, field, val)

        # Save files (only replace if a new upload was provided)
        for file_field in ("national_card_image", "business_license_image",
                           "latest_official_newspaper_image"):
            f = files.get(file_field)
            if f:
                err = _validate_file(f)
                if err:
                    errors.append(err)
                else:
                    setattr(profile, file_field, f)

        # Require national_card_image for first submission
        if not profile.national_card_image:
            errors.append("تصویر کارت ملی الزامی است.")

        # Require at least the core fields
        missing = [f for f in REQUIRED_FOR_SUBMISSION if not getattr(profile, f, "").strip()]
        if missing:
            errors.append("فیلدهای اجباری تکمیل نشده‌اند: " + "، ".join(missing))

        if errors:
            return errors

        from .models import CompanyMerchantProfile
        profile.status = CompanyMerchantProfile.Status.SUBMITTED
        profile.submitted_at = timezone.now()
        profile.rejected_reason = ""
        profile.save()
        return []

    @staticmethod
    def set_under_review(profile, reviewer) -> None:
        from .models import CompanyMerchantProfile
        profile.status = CompanyMerchantProfile.Status.UNDER_REVIEW
        profile.reviewed_by = reviewer
        profile.reviewed_at = timezone.now()
        profile.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

    @staticmethod
    def approve(profile, reviewer, note: str = "") -> None:
        from .models import CompanyMerchantProfile
        profile.status = CompanyMerchantProfile.Status.APPROVED
        profile.reviewed_by = reviewer
        profile.reviewed_at = timezone.now()
        profile.review_note = note
        profile.rejected_reason = ""
        profile.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "review_note",
            "rejected_reason", "updated_at",
        ])

    @staticmethod
    def reject(profile, reviewer, reason: str) -> None:
        from .models import CompanyMerchantProfile
        profile.status = CompanyMerchantProfile.Status.REJECTED
        profile.reviewed_by = reviewer
        profile.reviewed_at = timezone.now()
        profile.rejected_reason = reason
        profile.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "rejected_reason", "updated_at",
        ])

    @staticmethod
    def request_changes(profile, reviewer, note: str) -> None:
        from .models import CompanyMerchantProfile
        profile.status = CompanyMerchantProfile.Status.CHANGE_REQUESTED
        profile.reviewed_by = reviewer
        profile.reviewed_at = timezone.now()
        profile.review_note = note
        profile.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "review_note", "updated_at",
        ])


class MerchantProfileChangeRequestService:
    """
    Manages edit requests for already-approved merchant profiles.
    """

    @staticmethod
    def submit(profile, user, data: dict, files: dict) -> tuple["CompanyMerchantProfileChangeRequest | None", list[str]]:
        """
        Create a change request with proposed new values.

        Returns (request, errors). errors is empty on success.
        """
        from .models import CompanyMerchantProfileChangeRequest

        errors = []
        explanation = data.get("explanation", "").strip()

        # Collect proposed text changes
        proposed = {}
        for field in PROFILE_TEXT_FIELDS:
            proposed[field] = data.get(field, "").strip()

        # Validate any new files
        new_files = {}
        for file_field in ("national_card_image", "business_license_image",
                           "latest_official_newspaper_image"):
            f = files.get(file_field)
            if f:
                err = _validate_file(f)
                if err:
                    errors.append(err)
                else:
                    new_files[file_field] = f

        if errors:
            return None, errors

        req = CompanyMerchantProfileChangeRequest(
            company=profile.company,
            profile=profile,
            proposed_changes=proposed,
            explanation=explanation,
            created_by=user,
        )
        for file_field, f in new_files.items():
            setattr(req, file_field, f)
        req.save()
        return req, []

    @staticmethod
    def approve(change_request, reviewer, note: str = "") -> None:
        """Apply proposed changes to the profile and mark request approved."""
        from .models import CompanyMerchantProfileChangeRequest, CompanyMerchantProfile

        profile = change_request.profile
        for field in PROFILE_TEXT_FIELDS:
            val = change_request.proposed_changes.get(field)
            if val is not None:
                setattr(profile, field, val)

        # Apply new document uploads if present
        for file_field in ("national_card_image", "business_license_image",
                           "latest_official_newspaper_image"):
            f = getattr(change_request, file_field, None)
            if f:
                setattr(profile, file_field, f)

        profile.status = CompanyMerchantProfile.Status.APPROVED
        profile.reviewed_by = reviewer
        profile.reviewed_at = timezone.now()
        profile.review_note = note
        profile.save()

        change_request.status = CompanyMerchantProfileChangeRequest.Status.APPROVED
        change_request.reviewed_by = reviewer
        change_request.reviewed_at = timezone.now()
        change_request.review_note = note
        change_request.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "review_note",
        ])

    @staticmethod
    def reject(change_request, reviewer, reason: str) -> None:
        from .models import CompanyMerchantProfileChangeRequest

        change_request.status = CompanyMerchantProfileChangeRequest.Status.REJECTED
        change_request.reviewed_by = reviewer
        change_request.reviewed_at = timezone.now()
        change_request.review_note = reason
        change_request.save(update_fields=[
            "status", "reviewed_by", "reviewed_at", "review_note",
        ])


# ---------------------------------------------------------------------------
# Payment Eligibility
# ---------------------------------------------------------------------------

class CompanyPaymentEligibilityService:
    """
    Determines whether a company is eligible to use a real payment gateway.

    Returns (is_eligible: bool, reason: str).
    reason is empty string when eligible.
    """

    REQUIRED_FIELDS = [
        "legal_company_name", "owner_national_code", "postal_code",
        "registered_address", "company_phone", "owner_full_name",
        "owner_mobile", "bank_name", "account_holder_name", "shaba_number",
    ]

    @staticmethod
    def is_gateway_enabled(company) -> tuple[bool, str]:
        from .models import CompanyMerchantProfile

        if not company.is_active:
            return False, "company_inactive"

        try:
            profile = company.merchant_profile
        except CompanyMerchantProfile.DoesNotExist:
            return False, "no_merchant_profile"

        if profile.status != CompanyMerchantProfile.Status.APPROVED:
            return False, "merchant_profile_not_approved"

        for field in CompanyPaymentEligibilityService.REQUIRED_FIELDS:
            if not getattr(profile, field, "").strip():
                return False, f"missing_required_field"

        if not profile.national_card_image:
            return False, "missing_national_card_document"

        return True, ""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_ALLOWED_EXTENSIONS = {"jpg", "jpeg", "png", "pdf"}
_MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB


def _validate_file(f) -> str:
    """Return error string, or empty string if valid."""
    if f is None:
        return ""
    ext = f.name.rsplit(".", 1)[-1].lower() if "." in f.name else ""
    if ext not in _ALLOWED_EXTENSIONS:
        return f"فرمت فایل «{f.name}» مجاز نیست. فقط jpg، png و pdf قابل قبول است."
    if f.size > _MAX_FILE_SIZE:
        return f"حجم فایل «{f.name}» نباید بیشتر از ۵ مگابایت باشد."
    return ""
