"""Payments - Permissions."""
from django.http import HttpRequest


def can_manage_payments(request: HttpRequest) -> bool:
    role = getattr(request.user, "role", None)
    return role in ["COMPANY_ADMIN"]
