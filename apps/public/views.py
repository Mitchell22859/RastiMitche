"""
Public - Views.

Public-facing marketing/informational pages.
No authentication required.
"""
import logging

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .services import CompanyRegistrationService

logger = logging.getLogger(__name__)

registration_service = CompanyRegistrationService()


def home(request: HttpRequest) -> HttpResponse:
    """Landing page at /."""
    return render(request, "public/home.html")


def features(request: HttpRequest) -> HttpResponse:
    """Features page at /features/."""
    return render(request, "public/features.html")


def pricing(request: HttpRequest) -> HttpResponse:
    """Pricing page at /pricing/."""
    return render(request, "public/pricing.html")


def about(request: HttpRequest) -> HttpResponse:
    """About page at /about/."""
    return render(request, "public/about.html")


def contact(request: HttpRequest) -> HttpResponse:
    """Contact page at /contact/."""
    return render(request, "public/contact.html")


def register(request: HttpRequest) -> HttpResponse:
    """
    Company registration form at /register/.

    GET: Shows the registration form with all fields.
    POST: Validates data, stores in session, generates OTP, redirects to verify.
    """
    if request.method == "GET":
        # Pre-fill from session if user navigates back
        context = {
            "form_data": request.session.get("registration_data", {}),
            "errors": {},
        }
        return render(request, "public/register.html", context)

    # POST - process form
    data = {
        "company_name": request.POST.get("company_name", ""),
        "company_code": request.POST.get("company_code", ""),
        "company_phone": request.POST.get("company_phone", ""),
        "company_email": request.POST.get("company_email", ""),
        "city": request.POST.get("city", ""),
        "address": request.POST.get("address", ""),
        "admin_name": request.POST.get("admin_name", ""),
        "admin_username": request.POST.get("admin_username", ""),
        "admin_email": request.POST.get("admin_email", ""),
        "admin_phone": request.POST.get("admin_phone", ""),
        "password": request.POST.get("password", ""),
        "password_confirm": request.POST.get("password_confirm", ""),
        "service_types": request.POST.get("service_types", ""),
    }

    # Validate
    is_valid, errors = registration_service.validate_registration_data(data)

    if not is_valid:
        context = {
            "form_data": data,
            "errors": errors,
        }
        return render(request, "public/register.html", context)

    # Ensure session is created
    if not request.session.session_key:
        request.session.create()

    # Store in session
    registration_service.create_pending_registration(data, request.session)

    # Generate and send OTP
    phone = request.session["registration_data"]["admin_phone"]
    session_key = request.session.session_key
    code = registration_service.generate_and_send_otp(phone, session_key)

    # Store OTP send time for cooldown
    request.session["otp_sent_at"] = timezone.now().isoformat()
    request.session["otp_dev_code"] = code  # For dev display only
    request.session.modified = True

    return redirect("public:register_verify")


def register_verify(request: HttpRequest) -> HttpResponse:
    """
    OTP verification at /register/verify/.

    GET: Shows OTP input form.
    POST: Verifies OTP and completes registration.
    """
    # Check that registration data exists in session
    registration_data = request.session.get("registration_data")
    if not registration_data:
        return redirect("public:register")

    phone = registration_data.get("admin_phone", "")

    if request.method == "GET":
        # Mask phone for display: 0912***6789
        masked_phone = phone
        if len(phone) >= 11:
            masked_phone = phone[:4] + "***" + phone[7:]

        context = {
            "masked_phone": masked_phone,
            "error": "",
            "dev_code": request.session.get("otp_dev_code", ""),
        }
        return render(request, "public/register_verify.html", context)

    # POST - verify OTP
    code = request.POST.get("code", "").strip()
    session_key = request.session.session_key

    if not code:
        context = {
            "masked_phone": phone[:4] + "***" + phone[7:] if len(phone) >= 11 else phone,
            "error": "لطفاً کد تایید را وارد کنید.",
            "dev_code": request.session.get("otp_dev_code", ""),
        }
        return render(request, "public/register_verify.html", context)

    # Verify OTP
    is_valid = registration_service.verify_otp(phone, code, session_key)

    if not is_valid:
        context = {
            "masked_phone": phone[:4] + "***" + phone[7:] if len(phone) >= 11 else phone,
            "error": "کد تایید نامعتبر یا منقضی شده است.",
            "dev_code": request.session.get("otp_dev_code", ""),
        }
        return render(request, "public/register_verify.html", context)

    # OTP verified — complete registration
    try:
        company = registration_service.complete_registration(registration_data)
        logger.info(f"Company registered: {company.name} ({company.code})")
    except Exception as e:
        logger.error(f"Registration failed: {e}")
        context = {
            "masked_phone": phone[:4] + "***" + phone[7:] if len(phone) >= 11 else phone,
            "error": "خطا در ثبت‌نام. لطفاً دوباره تلاش کنید.",
            "dev_code": request.session.get("otp_dev_code", ""),
        }
        return render(request, "public/register_verify.html", context)

    # Clear session registration data
    for key in ["registration_data", "otp_sent_at", "otp_dev_code"]:
        request.session.pop(key, None)
    request.session.modified = True

    return redirect("public:register_success")


@require_POST
def register_resend_otp(request: HttpRequest) -> HttpResponse:
    """
    Resend OTP with 60-second cooldown.
    POST only.
    """
    registration_data = request.session.get("registration_data")
    if not registration_data:
        return redirect("public:register")

    phone = registration_data.get("admin_phone", "")

    # Check cooldown (60 seconds)
    otp_sent_at = request.session.get("otp_sent_at")
    if otp_sent_at:
        sent_time = timezone.datetime.fromisoformat(otp_sent_at)
        if timezone.is_naive(sent_time):
            sent_time = timezone.make_aware(sent_time)
        elapsed = (timezone.now() - sent_time).total_seconds()
        if elapsed < 60:
            remaining = int(60 - elapsed)
            return JsonResponse(
                {"success": False, "message": f"لطفاً {remaining} ثانیه صبر کنید."},
                status=429,
            )

    # Generate new OTP
    session_key = request.session.session_key
    code = registration_service.generate_and_send_otp(phone, session_key)

    # Update session
    request.session["otp_sent_at"] = timezone.now().isoformat()
    request.session["otp_dev_code"] = code
    request.session.modified = True

    return JsonResponse({"success": True, "message": "کد تایید مجدداً ارسال شد."})


def register_success(request: HttpRequest) -> HttpResponse:
    """Registration success at /register/success/."""
    return render(request, "public/register_success.html")
