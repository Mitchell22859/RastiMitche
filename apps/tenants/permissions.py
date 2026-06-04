"""
Tenants - Permissions.

Helpers to verify tenant-level access.
"""
from django.http import HttpRequest


def user_belongs_to_company(request: HttpRequest) -> bool:
    """
    Check if the authenticated user belongs to the current tenant (company).
    """
    if not request.user.is_authenticated:
        return False

    company = getattr(request, "company", None)
    if company is None:
        return False

    # CompanyUser has a company FK
    return getattr(request.user, "company_id", None) == company.id
