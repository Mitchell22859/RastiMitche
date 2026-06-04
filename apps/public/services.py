"""
Public - Registration Service.

Handles company self-registration flow:
1. Validate form data
2. Store in session (pending)
3. Generate and verify OTP
4. Complete registration (create Company + CompanyUser + CompanySettings + CompanyPage)
"""
import logging
import random
import re
import string

from django.utils import timezone

from apps.accounts.models import CompanyUser, RegistrationOTP, UserRole
from apps.sms.services import normalize_sms_phone_number
from apps.tenants.models import (
    Company,
    CompanyPage,
    CompanyServiceCategory,
    CompanySettings,
)

logger = logging.getLogger(__name__)

USERNAME_REGEX = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

RESERVED_SLUGS = {
    "login", "logout", "register", "owner-platform", "admin", "api",
    "static", "media", "pricing", "features", "about", "contact",
    "health", "dashboard", "tech", "customer", "payments", "invoices",
    "request", "favicon", "loginlogin",
}


class CompanyRegistrationService:
    """Service for company self-registration."""

    def validate_registration_data(self, data: dict) -> tuple[bool, dict]:
        """
        Validate registration form data.

        Checks:
        - company_code: required, URL-safe (slug), unique
        - admin_phone: required, valid Iranian mobile, unique
        - admin_username: required, 3-50 chars, matches USERNAME_REGEX, unique, not reserved
        - admin_email: required, valid email format
        - company_email: optional, validate format if provided
        - password: required, min 6 chars, matches password_confirm
        - company_name: required

        Returns:
            (is_valid, errors_dict)
        """
        errors = {}

        # Company name
        company_name = (data.get("company_name") or "").strip()
        if not company_name:
            errors["company_name"] = "نام شرکت الزامی است."

        # Company code
        company_code = (data.get("company_code") or "").strip().lower()
        if not company_code:
            errors["company_code"] = "کد شرکت الزامی است."
        elif not re.match(r"^[a-z0-9][a-z0-9_-]*$", company_code):
            errors["company_code"] = "کد شرکت فقط می‌تواند شامل حروف انگلیسی کوچک، اعداد، خط تیره و زیرخط باشد."
        elif Company.objects.filter(code=company_code).exists():
            errors["company_code"] = "این کد شرکت قبلاً استفاده شده است."

        # Company email (OPTIONAL — many Iranian service companies don't have one)
        company_email = (data.get("company_email") or "").strip().lower()
        if company_email:
            if "@" not in company_email or "." not in company_email.split("@")[-1]:
                errors["company_email"] = "فرمت ایمیل شرکت معتبر نیست."

        # Admin phone (for OTP only, NOT unique — same person may have multiple accounts)
        admin_phone = (data.get("admin_phone") or "").strip()
        if not admin_phone:
            errors["admin_phone"] = "شماره تلفن مدیر الزامی است."
        else:
            normalized = normalize_sms_phone_number(admin_phone)
            if normalized is None:
                errors["admin_phone"] = "شماره تلفن وارد شده معتبر نیست. فرمت صحیح: 09xxxxxxxxx"

        # Admin username
        admin_username = (data.get("admin_username") or "").strip().lower()
        if not admin_username:
            errors["admin_username"] = "نام کاربری الزامی است."
        elif len(admin_username) < 3:
            errors["admin_username"] = "نام کاربری باید حداقل ۳ کاراکتر باشد."
        elif len(admin_username) > 50:
            errors["admin_username"] = "نام کاربری حداکثر ۵۰ کاراکتر مجاز است."
        elif not USERNAME_REGEX.match(admin_username):
            errors["admin_username"] = "نام کاربری فقط می‌تواند شامل حروف انگلیسی کوچک، اعداد، _ و - باشد."
        elif admin_username in RESERVED_SLUGS:
            errors["admin_username"] = "این نام کاربری رزرو شده است."
        elif CompanyUser.objects.filter(username=admin_username).exists():
            errors["admin_username"] = "این نام کاربری قبلاً استفاده شده است."

        # Admin email
        # Admin email (format-only, NOT unique — same person may have multiple accounts)
        admin_email = (data.get("admin_email") or "").strip().lower()
        if not admin_email:
            errors["admin_email"] = "ایمیل مدیر الزامی است."
        elif "@" not in admin_email or "." not in admin_email.split("@")[-1]:
            errors["admin_email"] = "فرمت ایمیل مدیر معتبر نیست."

        # Password
        password = data.get("password") or ""
        password_confirm = data.get("password_confirm") or ""
        if not password:
            errors["password"] = "رمز عبور الزامی است."
        elif len(password) < 6:
            errors["password"] = "رمز عبور باید حداقل ۶ کاراکتر باشد."
        elif password != password_confirm:
            errors["password_confirm"] = "رمز عبور و تکرار آن مطابقت ندارند."

        is_valid = len(errors) == 0
        return is_valid, errors

    def create_pending_registration(self, data: dict, session) -> None:
        """
        Store registration data in Django session (NOT database).
        Data will be used after OTP verification to create the actual records.
        """
        normalized_phone = normalize_sms_phone_number(
            (data.get("admin_phone") or "").strip()
        )

        session["registration_data"] = {
            "company_name": (data.get("company_name") or "").strip(),
            "company_code": (data.get("company_code") or "").strip().lower(),
            "company_phone": (data.get("company_phone") or "").strip(),
            "company_email": (data.get("company_email") or "").strip().lower(),
            "city": (data.get("city") or "").strip(),
            "address": (data.get("address") or "").strip(),
            "admin_name": (data.get("admin_name") or "").strip(),
            "admin_username": (data.get("admin_username") or "").strip().lower(),
            "admin_email": (data.get("admin_email") or "").strip().lower(),
            "admin_phone": normalized_phone or "",
            "password": data.get("password") or "",
            "service_types": (data.get("service_types") or "").strip(),
        }
        session.modified = True

    def generate_and_send_otp(self, phone: str, session_key: str) -> str:
        """
        Generate 6-digit OTP, store in RegistrationOTP model,
        and send via console logger (dev mode).

        Returns the code for dev display.
        """
        code = "".join(random.choices(string.digits, k=6))

        # Store OTP
        RegistrationOTP.objects.create(
            phone=phone,
            code=code,
            session_key=session_key,
        )

        # Dev mode: log to console
        logger.info(f"[DEV OTP] Phone: {phone}, Code: {code}")

        return code

    def verify_otp(self, phone: str, code: str, session_key: str) -> bool:
        """
        Verify OTP code.

        Checks:
        - Matches phone and session_key
        - Not already used
        - Not expired (5 minute window)
        """
        expiry_time = timezone.now() - timezone.timedelta(minutes=5)

        otp = (
            RegistrationOTP.objects.filter(
                phone=phone,
                code=code,
                session_key=session_key,
                is_used=False,
                created_at__gte=expiry_time,
            )
            .order_by("-created_at")
            .first()
        )

        if otp is None:
            return False

        # Mark as used
        otp.is_used = True
        otp.save(update_fields=["is_used"])
        return True

    def complete_registration(self, session_data: dict) -> Company:
        """
        Create Company, CompanyUser (admin), CompanySettings, and CompanyPage.

        Company is created with is_active=False (pending platform owner review).
        """
        # Create Company
        company = Company.objects.create(
            name=session_data["company_name"],
            code=session_data["company_code"],
            slug=session_data["company_code"],
            is_active=False,  # Pending review
            email=session_data.get("company_email", ""),
            phone=session_data.get("company_phone", ""),
            address=session_data.get("address", ""),
        )

        # Create CompanyUser (admin)
        admin_name_parts = session_data.get("admin_name", "").split(" ", 1)
        first_name = admin_name_parts[0] if admin_name_parts else ""
        last_name = admin_name_parts[1] if len(admin_name_parts) > 1 else ""

        CompanyUser.objects.create_user(
            username=session_data["admin_username"],
            password=session_data["password"],
            company=company,
            role=UserRole.COMPANY_ADMIN,
            first_name=first_name,
            last_name=last_name,
            phone=session_data["admin_phone"],
            email=session_data.get("admin_email", ""),
        )

        # Create CompanySettings
        CompanySettings.objects.create(company=company)

        # Create CompanyPage
        CompanyPage.objects.create(
            company=company,
            title=session_data["company_name"],
        )

        # Create service categories if provided
        service_types = session_data.get("service_types", "")
        if service_types:
            for i, stype in enumerate(service_types.split(","), start=1):
                stype = stype.strip()
                if stype:
                    CompanyServiceCategory.objects.create(
                        company=company,
                        title=stype,
                        sort_order=i,
                    )

        try:
            from apps.sms.provisioning import provision_company_communication_defaults

            provision_company_communication_defaults(company)
        except Exception:
            # Registration must never fail because of notification/SMS provisioning.
            pass

        try:
            from apps.notifications.event_catalog import EventKey
            from apps.notifications.services_events import NotificationEventService

            NotificationEventService.emit(
                event_key=EventKey.COMPANY_REGISTERED,
                company=company,
                actor=None,
                target=company,
                payload={
                    "company_name": company.name,
                    "company_code": company.code,
                    "admin_name": session_data.get("admin_name", ""),
                    "admin_phone": session_data.get("admin_phone", ""),
                },
                dispatch=False,
            )
        except Exception:
            pass

        return company
