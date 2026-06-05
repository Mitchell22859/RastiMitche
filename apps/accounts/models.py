"""
Accounts - Models.

Custom user model and role system.
CompanyUser is the AUTH_USER_MODEL for this project.
"""
import hashlib
import secrets
from datetime import timedelta

from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.common.models import CompanyOwnedModel


class UserRole(models.TextChoices):
    """
    Role system for the platform.

    PLATFORM_OWNER: Full access to the platform admin panel (/loginlogin/).
    COMPANY_ADMIN:  Full access to a specific company's dashboard.
    COMPANY_STAFF:  Limited access to company dashboard (view/manage orders etc.).
    TECHNICIAN:     Mobile/field worker — sees assigned orders only.
    CUSTOMER:       End customer — can view their orders and invoices.
    """

    PLATFORM_OWNER = "PLATFORM_OWNER", "Platform Owner"
    COMPANY_ADMIN = "COMPANY_ADMIN", "Company Admin"
    COMPANY_STAFF = "COMPANY_STAFF", "Company Staff"
    TECHNICIAN = "TECHNICIAN", "Technician"
    CUSTOMER = "CUSTOMER", "Customer"


class CompanyUserManager(BaseUserManager):
    """Custom manager for CompanyUser."""

    def create_user(
        self, username: str, password: str | None = None, **extra_fields
    ) -> "CompanyUser":
        if not username:
            raise ValueError("Username is required.")
        user = self.model(username=username.lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(
        self, username: str, password: str | None = None, **extra_fields
    ) -> "CompanyUser":
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("role", UserRole.PLATFORM_OWNER)
        return self.create_user(username, password, **extra_fields)


class CompanyUser(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for the platform.

    - Platform owners have company=None and role=PLATFORM_OWNER.
    - All other users are scoped to a company.
    - Username is the primary login identifier.
    - Phone is used for OTP/contact only.
    """

    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="users",
        help_text="Null for platform owners.",
    )
    username = models.CharField(
        max_length=50,
        unique=True,
        db_index=True,
        help_text="Primary login identifier. Lowercase, letters/numbers/underscore/dash.",
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        help_text="Mobile phone for OTP/contact. Not unique — same person may have multiple accounts.",
    )
    email = models.EmailField(blank=True)
    first_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100, blank=True)
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.COMPANY_STAFF,
    )
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    must_change_password = models.BooleanField(default=False)
    password_changed_at = models.DateTimeField(null=True, blank=True)

    objects = CompanyUserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS: list[str] = []

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self) -> str:
        return f"{self.get_full_name()} ({self.username})"

    def get_full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip() or self.username


class Technician(CompanyOwnedModel):
    """
    Technician profile linked to a CompanyUser.
    Contains additional technician-specific fields.
    """

    user = models.OneToOneField(
        CompanyUser,
        on_delete=models.CASCADE,
        related_name="technician_profile",
    )
    national_id = models.CharField(max_length=20, blank=True)
    is_available = models.BooleanField(default=True)
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    notes = models.TextField(blank=True)

    # Wage percentage fields (Phase 16)
    service_wage_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="درصد سهم تکنسین از اجرت خدمات (0-100)",
    )
    goods_wage_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="درصد سهم تکنسین از کالا / قطعه (0-100)",
    )
    travel_wage_percent = models.DecimalField(
        max_digits=5, decimal_places=2, default=0,
        help_text="درصد سهم تکنسین از ایاب و ذهاب (0-100)",
    )

    def __str__(self) -> str:
        return f"Technician: {self.user.get_full_name()}"


class TechnicianSkill(CompanyOwnedModel):
    """Skills/specializations for technicians."""

    technician = models.ForeignKey(
        Technician,
        on_delete=models.CASCADE,
        related_name="skills",
    )
    name = models.CharField(max_length=100)
    level = models.CharField(
        max_length=20,
        choices=[
            ("beginner", "Beginner"),
            ("intermediate", "Intermediate"),
            ("expert", "Expert"),
        ],
        default="intermediate",
    )

    class Meta:
        unique_together = ["technician", "name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.level})"


class TechnicianCategorySkill(models.Model):
    """
    Maps a technician to a service category with a priority level.

    Priority determines order visibility timing:
    - Priority 1: sees the order immediately
    - Priority 2: sees the order after priority2_delay_minutes
    - Priority 3: sees the order after priority3_delay_minutes

    Each technician can have at most one priority per category.
    """

    class Priority(models.IntegerChoices):
        P1 = 1, "Priority 1"
        P2 = 2, "Priority 2"
        P3 = 3, "Priority 3"

    technician = models.ForeignKey(
        Technician,
        on_delete=models.CASCADE,
        related_name="category_skills",
    )
    category = models.ForeignKey(
        "tenants.CompanyServiceCategory",
        on_delete=models.CASCADE,
        related_name="technician_skills",
    )
    priority = models.IntegerField(choices=Priority.choices, default=Priority.P1)

    class Meta:
        ordering = ("priority", "id")
        constraints = [
            models.UniqueConstraint(
                fields=["technician", "category"],
                name="unique_technician_category_skill",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.technician} → {self.category} (P{self.priority})"


class Customer(CompanyOwnedModel):
    """
    Customer model for each company.
    Customers are end-users who request services.
    """

    user = models.OneToOneField(
        CompanyUser,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="customer_profile",
    )
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        unique_together = ["company", "phone"]

    def __str__(self) -> str:
        return f"{self.first_name} {self.last_name} ({self.phone})"


class OperatorPermission(models.Model):
    """
    Per-company, per-operator access rule.

    Future admin URLs are discovered dynamically from tenant URL patterns.
    New pages appear in the admin permission list automatically.
    """
    company = models.ForeignKey(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="operator_permissions",
    )
    operator = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="operator_permissions",
    )
    permission_key = models.CharField(max_length=180)
    is_allowed = models.BooleanField(default=False)

    class Meta:
        ordering = ["operator_id", "permission_key"]
        constraints = [
            models.UniqueConstraint(
                fields=["company", "operator", "permission_key"],
                name="unique_operator_permission_per_company_operator_key",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company_id}:{self.operator_id}:{self.permission_key}={self.is_allowed}"




class RegistrationOTP(models.Model):
    """
    OTP codes for company registration verification.
    Links to session via session_key, expires after 5 minutes.
    """

    phone = models.CharField(max_length=15)
    code = models.CharField(max_length=6)
    created_at = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    session_key = models.CharField(max_length=64)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"OTP: {self.phone} ({self.code})"


class PasswordResetOTP(models.Model):
    """
    Phone-based OTP for password reset.
    Linked to a phone number, NOT to a specific user.
    Account selection happens AFTER OTP verification to prevent enumeration.
    OTP expires after 2 minutes. Single-use. Max 5 attempts.
    Code is never stored in plain text — only SHA-256 hash.
    """

    MAX_ATTEMPTS = 5
    EXPIRY_SECONDS = 120
    RESEND_COOLDOWN_SECONDS = 60

    phone = models.CharField(max_length=15, db_index=True)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    is_used = models.BooleanField(default=False)
    attempt_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"PasswordResetOTP: {self.phone} (used={self.is_used})"

    @property
    def is_expired(self) -> bool:
        return timezone.now() >= self.expires_at

    @classmethod
    def can_send(cls, phone: str) -> bool:
        """Rate-limit: True only if no OTP was created in the last RESEND_COOLDOWN_SECONDS."""
        cutoff = timezone.now() - timedelta(seconds=cls.RESEND_COOLDOWN_SECONDS)
        return not cls.objects.filter(phone=phone, created_at__gte=cutoff).exists()

    @classmethod
    def generate_for_phone(cls, phone: str) -> tuple["PasswordResetOTP", str]:
        """Invalidate previous OTPs for this phone, generate new 6-digit code."""
        cls.objects.filter(phone=phone, is_used=False).update(is_used=True)
        plain = "".join(str(secrets.randbelow(10)) for _ in range(6))
        code_hash = hashlib.sha256(plain.encode()).hexdigest()
        otp = cls.objects.create(
            phone=phone,
            code_hash=code_hash,
            expires_at=timezone.now() + timedelta(seconds=cls.EXPIRY_SECONDS),
        )
        return otp, plain

    def check_code(self, plain: str) -> bool:
        """Verify code. Increments attempt counter. Returns True only if valid."""
        if self.is_used or self.is_expired or self.attempt_count >= self.MAX_ATTEMPTS:
            return False
        self.attempt_count += 1
        self.save(update_fields=["attempt_count"])
        return self.code_hash == hashlib.sha256(plain.encode()).hexdigest()

    def consume(self) -> None:
        self.is_used = True
        self.save(update_fields=["is_used"])


class PasswordResetSMSBillingPolicy(models.Model):
    """
    Per-company configuration of who pays for password reset SMS.
    Default for all roles is PLATFORM (platform owner pays).
    Platform owner can change per-company to charge the company for specific roles.
    """

    class Payer(models.TextChoices):
        PLATFORM = "PLATFORM", "مالک پلتفرم"
        COMPANY = "COMPANY", "شرکت"

    company = models.OneToOneField(
        "tenants.Company",
        on_delete=models.CASCADE,
        related_name="password_reset_sms_policy",
    )
    company_admin_payer = models.CharField(
        max_length=20, choices=Payer.choices, default=Payer.PLATFORM,
        verbose_name="مدیر شرکت",
    )
    operator_payer = models.CharField(
        max_length=20, choices=Payer.choices, default=Payer.PLATFORM,
        verbose_name="اپراتور",
    )
    technician_payer = models.CharField(
        max_length=20, choices=Payer.choices, default=Payer.PLATFORM,
        verbose_name="نیروی خدماتی",
    )
    customer_payer = models.CharField(
        max_length=20, choices=Payer.choices, default=Payer.PLATFORM,
        verbose_name="مشتری",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company__name"]
        verbose_name = "Password Reset SMS Billing Policy"

    def __str__(self) -> str:
        return f"PasswordResetSMSBillingPolicy: {self.company}"

    def get_payer_for_role(self, role: str) -> str:
        mapping = {
            UserRole.COMPANY_ADMIN: self.company_admin_payer,
            UserRole.COMPANY_STAFF: self.operator_payer,
            UserRole.TECHNICIAN: self.technician_payer,
            UserRole.CUSTOMER: self.customer_payer,
        }
        return mapping.get(role, self.Payer.PLATFORM)
