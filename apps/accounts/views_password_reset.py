"""
Secure multi-tenant password reset flow.

Anti-enumeration design:
  - Generic response on every submit regardless of whether account exists
  - Account list revealed ONLY after OTP is verified
  - Phone ownership proven before showing which companies/roles exist

Flow:
  1. /password-reset/         → enter identifier + captcha → always generic response
  2. /password-reset/verify/  → enter 6-digit OTP (resend also requires captcha)
  3. /password-reset/select/  → pick account IF multiple match (AFTER OTP verified)
  4. /password-reset/confirm/ → set new password

Security controls:
  - Captcha required on OTP request and resend
  - Rate limit: 60s cooldown between OTP sends per phone
  - OTP expires after 2 minutes
  - OTP is hashed (SHA-256), never stored plain
  - Max 5 incorrect OTP attempts
  - Account list only shown post-OTP

SMS billing:
  - Default payer: PLATFORM
  - Configurable per-company/per-role via PasswordResetSMSBillingPolicy
"""
from __future__ import annotations

import random
import re

from django.conf import settings
from django.contrib.auth import login as auth_login
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import (
    CompanyUser,
    PasswordResetOTP,
    PasswordResetSMSBillingPolicy,
    UserRole,
)


# ── Constants ─────────────────────────────────────────────────────────────────

_PHONE_RE = re.compile(r"^09[0-9]{9}$")

ROLE_LABELS = {
    UserRole.PLATFORM_OWNER: "مالک پلتفرم",
    UserRole.COMPANY_ADMIN: "مدیر شرکت",
    UserRole.COMPANY_STAFF: "اپراتور",
    UserRole.TECHNICIAN: "نیروی خدماتی",
    UserRole.CUSTOMER: "مشتری",
}

_GENERIC_RESPONSE = (
    "اگر اطلاعات واردشده صحیح باشد، کد بازیابی به شماره موبایل مرتبط ارسال می‌شود."
)

# ── Session keys ─────────────────────────────────────────────────────────────

_SK_PHONE = "pr_phone"              # normalized phone to which OTP was sent
_SK_OTP_ID = "pr_otp_id"           # PasswordResetOTP.pk
_SK_DEV_CODE = "pr_dev_code"       # plain OTP shown only in DEBUG mode
_SK_CAPTCHA = "pr_captcha"         # expected captcha int answer
_SK_VERIFIED_PHONE = "pr_verified_phone"  # phone after successful OTP verification
_SK_CANDIDATES = "pr_candidates"   # list of user PKs (revealed after OTP)
_SK_VERIFIED_UID = "pr_verified_uid"     # chosen user PK after selection


def _clear_reset_session(session) -> None:
    for k in (_SK_PHONE, _SK_OTP_ID, _SK_DEV_CODE, _SK_CAPTCHA,
              _SK_VERIFIED_PHONE, _SK_CANDIDATES, _SK_VERIFIED_UID):
        session.pop(k, None)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize_phone(raw: str) -> str | None:
    if not raw:
        return None
    phone = re.sub(r"[\s\-\(\)]+", "", raw.strip())
    for fa, en in zip("۰۱۲۳۴۵۶۷۸۹", "0123456789"):
        phone = phone.replace(fa, en)
    for ar, en in zip("٠١٢٣٤٥٦٧٨٩", "0123456789"):
        phone = phone.replace(ar, en)
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0098"):
        phone = "0" + phone[4:]
    elif phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]
    elif phone.startswith("9") and len(phone) == 10:
        phone = "0" + phone
    return phone if _PHONE_RE.match(phone) else None


def _mask_phone(phone: str) -> str:
    if len(phone) >= 7:
        return phone[:4] + "***" + phone[-3:]
    return "***"


def _lookup_users_by_identifier(identifier: str) -> list[CompanyUser]:
    """Look up active users by username (exact) or phone (normalized). Silent."""
    identifier = identifier.strip()
    if not identifier:
        return []
    qs = CompanyUser.objects.filter(is_active=True).select_related("company")
    normalized = _normalize_phone(identifier)
    if normalized:
        return list(qs.filter(phone=normalized).order_by("role", "id"))
    return list(qs.filter(username__iexact=identifier).order_by("role", "id"))


def _lookup_users_by_phone(phone: str) -> list[CompanyUser]:
    return list(
        CompanyUser.objects.filter(phone=phone, is_active=True)
        .select_related("company")
        .order_by("role", "id")
    )


def _get_phone_for_users(users: list[CompanyUser], identifier: str) -> str | None:
    """Return the phone to send OTP to, or None if no valid phone exists."""
    if not users:
        return None
    phone = _normalize_phone(identifier)
    if phone:
        return phone
    # Looked up by username — use the user's stored phone
    first = users[0]
    return _normalize_phone(first.phone or "") or None


def _get_payer(users: list[CompanyUser]) -> str:
    """
    Determine SMS payer for a password reset.
    Returns 'PLATFORM' or 'COMPANY'.
    Default is always PLATFORM unless policy says otherwise.
    Only charges COMPANY when all matched users are from the same company
    and the policy for their role says COMPANY.
    """
    company_scoped = [u for u in users
                      if u.company_id and u.role != UserRole.PLATFORM_OWNER]
    if not company_scoped:
        return "PLATFORM"

    company_ids = {u.company_id for u in company_scoped}
    if len(company_ids) != 1:
        return "PLATFORM"

    company = company_scoped[0].company
    try:
        policy = PasswordResetSMSBillingPolicy.objects.get(company=company)
    except PasswordResetSMSBillingPolicy.DoesNotExist:
        return "PLATFORM"

    for u in company_scoped:
        if policy.get_payer_for_role(u.role) == PasswordResetSMSBillingPolicy.Payer.COMPANY:
            return "COMPANY"

    return "PLATFORM"


def _send_reset_sms(phone: str, otp_code: str, users: list[CompanyUser]) -> None:
    """
    Queue password reset OTP SMS. Never raises.
    Uses PlatformSMSOutbox (payer=PLATFORM) or SMSOutbox (payer=COMPANY).
    Bypasses event-switch service — OTP sends must never be blocked by company settings.
    """
    try:
        payer = _get_payer(users)
        company_name = "رستی سرویس"
        company_obj = None

        company_scoped = [u for u in users if u.company_id]
        if company_scoped:
            cids = {u.company_id for u in company_scoped}
            if len(cids) == 1:
                company_obj = company_scoped[0].company
                company_name = company_obj.name

        message = (
            f"«{company_name}»\n"
            f"کد بازیابی رمز عبور شما: {otp_code}\n"
            f"اعتبار: ۲ دقیقه"
        )

        if payer == "COMPANY" and company_obj:
            from apps.sms.models import SMSOutbox
            SMSOutbox.objects.create(
                company=company_obj,
                phone_number=phone,
                message=message,
                template_key="company_user_password_reset",
                status=SMSOutbox.Status.QUEUED,
                queued_at=timezone.now(),
            )
        else:
            from apps.platform_core.models import PlatformSMSOutbox, PlatformSMSMessageTypeSetting
            PlatformSMSOutbox.objects.create(
                recipient_company=company_obj,
                phone_number=phone,
                message=message,
                template_key=PlatformSMSMessageTypeSetting.MessageKey.PASSWORD_RESET,
                status=PlatformSMSOutbox.Status.QUEUED,
            )
    except Exception:
        pass


# ── Captcha ───────────────────────────────────────────────────────────────────

def _generate_captcha(session) -> str:
    """Generate a simple math captcha. Store answer in session. Return question string."""
    a = random.randint(2, 9)
    b = random.randint(1, 9)
    if random.choice([True, False]) and a >= b:
        question = f"{a} - {b}"
        answer = a - b
    else:
        question = f"{a} + {b}"
        answer = a + b
    session[_SK_CAPTCHA] = answer
    return question


def _verify_captcha(session, submitted: str) -> bool:
    expected = session.get(_SK_CAPTCHA)
    if expected is None:
        return False
    try:
        return int(submitted.strip()) == expected
    except (ValueError, AttributeError):
        return False


# ── Step 1: Request reset ─────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def password_reset_form(request: HttpRequest) -> HttpResponse:
    if request.method == "GET":
        _clear_reset_session(request.session)
        captcha_q = _generate_captcha(request.session)
        return render(request, "accounts/password_reset_form.html", {
            "captcha_question": captcha_q,
        })

    identifier = request.POST.get("identifier", "").strip()
    captcha_answer = request.POST.get("captcha", "").strip()

    if not _verify_captcha(request.session, captcha_answer):
        captcha_q = _generate_captcha(request.session)
        return render(request, "accounts/password_reset_form.html", {
            "error": "پاسخ محاسبه اشتباه است. لطفاً دوباره تلاش کنید.",
            "identifier": identifier,
            "captcha_question": captcha_q,
        })

    if not identifier:
        captcha_q = _generate_captcha(request.session)
        return render(request, "accounts/password_reset_form.html", {
            "error": "لطفاً نام کاربری یا شماره موبایل را وارد کنید.",
            "captcha_question": captcha_q,
        })

    # Silently look up users — do not reveal result to requestor
    users = _lookup_users_by_identifier(identifier)
    phone = _get_phone_for_users(users, identifier)

    _clear_reset_session(request.session)

    if phone and users and PasswordResetOTP.can_send(phone):
        otp, plain = PasswordResetOTP.generate_for_phone(phone)
        _send_reset_sms(phone, plain, users)
        request.session[_SK_PHONE] = phone
        request.session[_SK_OTP_ID] = otp.pk
        if settings.DEBUG:
            request.session[_SK_DEV_CODE] = plain
    elif phone and users:
        # Rate-limited — still redirect silently; OTP step will handle
        existing = PasswordResetOTP.objects.filter(
            phone=phone, is_used=False
        ).order_by("-created_at").first()
        if existing:
            request.session[_SK_PHONE] = phone
            request.session[_SK_OTP_ID] = existing.pk
            if settings.DEBUG:
                # Don't reveal plain code of previous OTP
                pass

    # Always show generic message — never reveal account existence
    return render(request, "accounts/password_reset_form.html", {
        "info": _GENERIC_RESPONSE,
        "show_verify_link": bool(request.session.get(_SK_OTP_ID)),
    })


# ── Step 2: Verify OTP ────────────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def password_reset_verify(request: HttpRequest) -> HttpResponse:
    otp_id = request.session.get(_SK_OTP_ID)
    phone = request.session.get(_SK_PHONE)
    dev_code = request.session.get(_SK_DEV_CODE) if settings.DEBUG else None

    # GET
    if request.method == "GET":
        if not otp_id or not phone:
            return redirect("password_reset")
        captcha_q = _generate_captcha(request.session)
        return render(request, "accounts/password_reset_otp.html", {
            "dev_code": dev_code,
            "phone_masked": _mask_phone(phone) if phone else "***",
            "captcha_question": captcha_q,
        })

    # POST — two possible actions: verify OTP or resend
    action = request.POST.get("action", "verify")

    if action == "resend":
        captcha_answer = request.POST.get("captcha", "").strip()
        if not _verify_captcha(request.session, captcha_answer):
            captcha_q = _generate_captcha(request.session)
            return render(request, "accounts/password_reset_otp.html", {
                "error": "پاسخ محاسبه اشتباه است.",
                "dev_code": dev_code,
                "phone_masked": _mask_phone(phone) if phone else "***",
                "captcha_question": captcha_q,
            })

        if not phone:
            return redirect("password_reset")

        if not PasswordResetOTP.can_send(phone):
            captcha_q = _generate_captcha(request.session)
            return render(request, "accounts/password_reset_otp.html", {
                "error": "لطفاً چند لحظه صبر کنید و سپس مجدداً درخواست کد دهید.",
                "dev_code": dev_code,
                "phone_masked": _mask_phone(phone) if phone else "***",
                "captcha_question": captcha_q,
            })

        users = _lookup_users_by_phone(phone)
        otp, plain = PasswordResetOTP.generate_for_phone(phone)
        _send_reset_sms(phone, plain, users)
        request.session[_SK_OTP_ID] = otp.pk
        if settings.DEBUG:
            request.session[_SK_DEV_CODE] = plain
            dev_code = plain

        captcha_q = _generate_captcha(request.session)
        return render(request, "accounts/password_reset_otp.html", {
            "info": "کد جدید ارسال شد.",
            "dev_code": dev_code,
            "phone_masked": _mask_phone(phone) if phone else "***",
            "captcha_question": captcha_q,
        })

    # action == "verify"
    if not otp_id or not phone:
        return redirect("password_reset")

    code = request.POST.get("otp_code", "").strip()
    if not code:
        captcha_q = _generate_captcha(request.session)
        return render(request, "accounts/password_reset_otp.html", {
            "error": "لطفاً کد بازیابی را وارد کنید.",
            "dev_code": dev_code,
            "phone_masked": _mask_phone(phone) if phone else "***",
            "captcha_question": captcha_q,
        })

    try:
        otp = PasswordResetOTP.objects.get(pk=otp_id, phone=phone, is_used=False)
    except PasswordResetOTP.DoesNotExist:
        _clear_reset_session(request.session)
        return render(request, "accounts/password_reset_otp.html", {
            "error": "کد بازیابی نامعتبر یا منقضی شده است. لطفاً دوباره درخواست دهید.",
            "show_restart": True,
        })

    if otp.is_expired:
        _clear_reset_session(request.session)
        return render(request, "accounts/password_reset_otp.html", {
            "error": "زمان کد بازیابی منقضی شده است. لطفاً دوباره درخواست دهید.",
            "show_restart": True,
        })

    if otp.attempt_count >= PasswordResetOTP.MAX_ATTEMPTS:
        _clear_reset_session(request.session)
        return render(request, "accounts/password_reset_otp.html", {
            "error": "تعداد تلاش‌های مجاز به پایان رسید. لطفاً دوباره درخواست دهید.",
            "show_restart": True,
        })

    if not otp.check_code(code):
        remaining = PasswordResetOTP.MAX_ATTEMPTS - otp.attempt_count
        captcha_q = _generate_captcha(request.session)
        return render(request, "accounts/password_reset_otp.html", {
            "error": f"کد وارد شده اشتباه است. {remaining} تلاش باقی‌مانده.",
            "dev_code": dev_code,
            "phone_masked": _mask_phone(phone) if phone else "***",
            "captcha_question": captcha_q,
        })

    # OTP correct — NOW reveal accounts for this phone
    otp.consume()
    users = _lookup_users_by_phone(phone)

    request.session.pop(_SK_OTP_ID, None)
    request.session.pop(_SK_PHONE, None)
    request.session.pop(_SK_DEV_CODE, None)
    request.session.pop(_SK_CAPTCHA, None)
    request.session[_SK_VERIFIED_PHONE] = phone

    if not users:
        _clear_reset_session(request.session)
        return render(request, "accounts/password_reset_otp.html", {
            "error": "حساب کاربری مرتبط یافت نشد. لطفاً با پشتیبانی تماس بگیرید.",
            "show_restart": True,
        })

    if len(users) == 1:
        request.session[_SK_VERIFIED_UID] = users[0].pk
        return redirect("password_reset_confirm")

    request.session[_SK_CANDIDATES] = [u.pk for u in users]
    return redirect("password_reset_select")


# ── Step 3: Account selection (only after OTP verified) ───────────────────────

@require_http_methods(["GET", "POST"])
def password_reset_select(request: HttpRequest) -> HttpResponse:
    verified_phone = request.session.get(_SK_VERIFIED_PHONE)
    candidate_ids = request.session.get(_SK_CANDIDATES)

    if not verified_phone or not candidate_ids:
        return redirect("password_reset")

    users = list(
        CompanyUser.objects.filter(pk__in=candidate_ids, is_active=True)
        .select_related("company")
        .order_by("role", "id")
    )
    if not users:
        _clear_reset_session(request.session)
        return redirect("password_reset")

    accounts = [
        {
            "pk": u.pk,
            "username": u.username,
            "role_label": ROLE_LABELS.get(u.role, u.role),
            "company_name": u.company.name if u.company else "پلتفرم",
            "company_code": u.company.code if u.company else "-",
            "phone_masked": _mask_phone(u.phone) if u.phone else "-",
        }
        for u in users
    ]

    if request.method == "GET":
        return render(request, "accounts/password_reset_select.html", {
            "accounts": accounts,
        })

    selected_pk_str = request.POST.get("user_pk", "").strip()
    if not selected_pk_str or not selected_pk_str.isdigit():
        return render(request, "accounts/password_reset_select.html", {
            "accounts": accounts,
            "error": "لطفاً یک حساب کاربری را انتخاب کنید.",
        })

    selected_pk = int(selected_pk_str)
    if selected_pk not in candidate_ids:
        return render(request, "accounts/password_reset_select.html", {
            "accounts": accounts,
            "error": "حساب انتخاب‌شده معتبر نیست.",
        })

    request.session.pop(_SK_CANDIDATES, None)
    request.session[_SK_VERIFIED_UID] = selected_pk
    return redirect("password_reset_confirm")


# ── Step 4: Set new password ──────────────────────────────────────────────────

@require_http_methods(["GET", "POST"])
def password_reset_confirm(request: HttpRequest) -> HttpResponse:
    verified_uid = request.session.get(_SK_VERIFIED_UID)
    if not verified_uid:
        return redirect("password_reset")

    try:
        user = CompanyUser.objects.get(pk=verified_uid, is_active=True)
    except CompanyUser.DoesNotExist:
        _clear_reset_session(request.session)
        return redirect("password_reset")

    if request.method == "GET":
        return render(request, "accounts/password_reset_confirm.html", {})

    password1 = request.POST.get("password1", "")
    password2 = request.POST.get("password2", "")

    if not password1:
        return render(request, "accounts/password_reset_confirm.html", {
            "error": "رمز عبور جدید را وارد کنید.",
        })
    if password1 != password2:
        return render(request, "accounts/password_reset_confirm.html", {
            "error": "رمزهای عبور با هم مطابقت ندارند.",
        })

    try:
        validate_password(password1, user=user)
    except ValidationError as exc:
        return render(request, "accounts/password_reset_confirm.html", {
            "error": " ".join(exc.messages),
        })

    user.set_password(password1)
    user.save(update_fields=["password", "updated_at"])
    _clear_reset_session(request.session)

    auth_login(request, user, backend="django.contrib.auth.backends.ModelBackend")
    from apps.accounts.services import RedirectService
    return redirect(RedirectService.get_post_login_url(user=user))

