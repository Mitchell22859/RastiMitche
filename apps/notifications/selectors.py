"""
Notifications - Selectors.

All read operations for notifications. ALWAYS company-scoped.
"""
from django.db.models import QuerySet

from apps.accounts.models import CompanyUser

from .models import Notification


class NotificationSelector:
    """Read operations for Notifications."""

    @staticmethod
    def get_for_user(*, company, user: CompanyUser) -> QuerySet[Notification]:
        """Get all notifications for a user within their company."""
        return Notification.objects.filter(company=company, recipient=user)

    @staticmethod
    def get_unread_for_user(*, company, user: CompanyUser) -> QuerySet[Notification]:
        """Get unread notifications for a user."""
        return Notification.objects.filter(
            company=company, recipient=user, is_read=False
        )

    @staticmethod
    def get_unread_count(*, company, user: CompanyUser) -> int:
        """Get unread notification count."""
        return Notification.objects.filter(
            company=company, recipient=user, is_read=False
        ).count()

    @staticmethod
    def get_for_company(*, company) -> QuerySet[Notification]:
        """Get all notifications for a company (admin view)."""
        return Notification.objects.filter(company=company)
