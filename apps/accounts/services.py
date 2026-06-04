"""
Accounts - Service Layer.

All authentication and user write operations.
Business logic MUST live here, never in views.
"""
from typing import Any, Optional

from django.contrib.auth import authenticate, login, logout
from django.http import HttpRequest

from .models import CompanyUser, Customer, Technician, UserRole


# =============================================================================
# AUTHENTICATION SERVICE
# =============================================================================


class AuthenticationService:
    """
    Centralized authentication logic.

    Rules:
    - Platform login: user must be PLATFORM_OWNER, no company required.
    - Tenant login: user must belong to the same company as request.company.
    - Inactive users cannot login.
    - Inactive companies block login (handled by middleware before reaching here).
    """

    @staticmethod
    def authenticate_platform_user(
        *, request: HttpRequest, phone: str, password: str
    ) -> tuple[Optional[CompanyUser], str]:
        """
        Authenticate a platform owner for /loginlogin/.

        Returns:
            (user, error_message) — user is None on failure.
        """
        user = authenticate(request, username=phone, password=password)

        if user is None:
            return None, "Invalid credentials."

        if not user.is_active:
            return None, "Account is inactive."

        if user.role != UserRole.PLATFORM_OWNER:
            return None, "Access denied. Platform owners only."

        return user, ""

    @staticmethod
    def authenticate_tenant_user(
        *, request: HttpRequest, phone: str, password: str
    ) -> tuple[Optional[CompanyUser], str]:
        """
        Authenticate a tenant user for /<company_code>/login/.

        Rules:
        - User must exist and credentials must be valid.
        - User must be active.
        - User must belong to the same company as request.company.
        - Platform owners cannot login via tenant URLs.

        Returns:
            (user, error_message) — user is None on failure.
        """
        company = getattr(request, "company", None)
        if company is None:
            return None, "Company not found."

        user = authenticate(request, username=phone, password=password)

        if user is None:
            return None, "Invalid credentials."

        if not user.is_active:
            return None, "Account is inactive."

        # Platform owners must use /loginlogin/
        if user.role == UserRole.PLATFORM_OWNER:
            return None, "Access denied."

        # Tenant isolation: user must belong to THIS company
        if user.company_id != company.id:
            return None, "Invalid credentials."

        return user, ""

    @staticmethod
    def login_user(*, request: HttpRequest, user: CompanyUser) -> None:
        """Create session for the authenticated user."""
        login(request, user)

    @staticmethod
    def logout_user(*, request: HttpRequest) -> None:
        """Destroy user session."""
        logout(request)


# =============================================================================
# ROLE-BASED REDIRECT SERVICE
# =============================================================================


class RedirectService:
    """
    Determines where to redirect a user after login based on their role.
    Centralized to avoid duplication across views.
    """

    @staticmethod
    def get_post_login_url(*, user: CompanyUser, company_code: Optional[str] = None) -> str:
        """
        Get the redirect URL after successful login.

        Args:
            user: The authenticated user.
            company_code: The tenant company code (for tenant users).

        Returns:
            URL path to redirect to.
        """
        if user.role == UserRole.PLATFORM_OWNER:
            return "/owner-platform/dashboard/"

        if not company_code and user.company:
            company_code = user.company.code

        if not company_code:
            return "/"

        role_redirects = {
            UserRole.COMPANY_ADMIN: f"/{company_code}/admin/",
            UserRole.COMPANY_STAFF: f"/{company_code}/admin/",
            UserRole.TECHNICIAN: f"/{company_code}/tech/",
            UserRole.CUSTOMER: f"/{company_code}/",
        }

        return role_redirects.get(user.role, f"/{company_code}/")


# =============================================================================
# USER MANAGEMENT SERVICES (from Phase 1, preserved)
# =============================================================================


class CompanyUserService:
    """Write operations for CompanyUser."""

    @staticmethod
    def create_company_user(*, data: dict[str, Any]) -> CompanyUser:
        """Create a new user for a company."""
        password = data.pop("password", None)
        user = CompanyUser(**data)
        if password:
            user.set_password(password)
        user.full_clean()
        user.save()
        return user


class TechnicianService:
    """Write operations for Technicians."""

    @staticmethod
    def create_technician(*, user: CompanyUser, company, **kwargs) -> Technician:
        """Create a technician profile for a user."""
        user.role = UserRole.TECHNICIAN
        user.save(update_fields=["role"])

        technician = Technician(user=user, company=company, **kwargs)
        technician.full_clean()
        technician.save()
        return technician


class CustomerService:
    """Write operations for Customers."""

    @staticmethod
    def create_customer(*, data: dict[str, Any]) -> Customer:
        """Create a new customer for a company."""
        customer = Customer(**data)
        customer.full_clean()
        customer.save()
        return customer
