"""
API - Permissions.

DRF permission classes for tenant-aware API access control.
These enforce the same rules as the web views:
- Tenant isolation
- Role-based access
- No cross-company data access

IMPORTANT: These use request.company set by TenantMiddleware.
"""
from rest_framework.permissions import BasePermission

from apps.accounts.models import UserRole


class IsTenantUser(BasePermission):
    """
    Ensures the user is authenticated AND belongs to the current tenant.
    Uses request.company (set by TenantMiddleware).
    """

    def has_permission(self, request, view) -> bool:
        company = getattr(request, "company", None)
        if not company:
            return False
        if not request.user or not request.user.is_authenticated:
            return False
        return getattr(request.user, "company_id", None) == company.id


class IsTenantAdminOrStaff(BasePermission):
    """Requires COMPANY_ADMIN or COMPANY_STAFF role within the tenant."""

    def has_permission(self, request, view) -> bool:
        company = getattr(request, "company", None)
        if not company:
            return False
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "company_id", None) != company.id:
            return False
        return request.user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]


class IsTenantTechnician(BasePermission):
    """Requires TECHNICIAN role within the tenant."""

    def has_permission(self, request, view) -> bool:
        company = getattr(request, "company", None)
        if not company:
            return False
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "company_id", None) != company.id:
            return False
        return request.user.role == UserRole.TECHNICIAN


class IsTenantCustomer(BasePermission):
    """Requires CUSTOMER role within the tenant."""

    def has_permission(self, request, view) -> bool:
        company = getattr(request, "company", None)
        if not company:
            return False
        if not request.user or not request.user.is_authenticated:
            return False
        if getattr(request.user, "company_id", None) != company.id:
            return False
        return request.user.role == UserRole.CUSTOMER


class IsPlatformOwner(BasePermission):
    """Requires PLATFORM_OWNER role. No tenant required."""

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False
        return request.user.role == UserRole.PLATFORM_OWNER
