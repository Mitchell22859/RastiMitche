"""
Invoices - Permissions.
"""
from django.http import HttpRequest


def can_manage_invoices(request: HttpRequest) -> bool:
    role = getattr(request.user, "role", None)
    return role in ["COMPANY_ADMIN", "COMPANY_STAFF"]
