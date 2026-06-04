"""
Platform Core - Selectors.

Read operations for platform-level resources.
These do NOT require request.company — they are global.
Only accessible by PLATFORM_OWNER.
"""
from typing import Optional

from django.db.models import Count, QuerySet

from apps.orders.models import Order
from apps.tenants.models import Company

from .models import Plan, Subscription


class PlatformCompanySelector:
    """Read operations for Companies (platform-level view)."""

    @staticmethod
    def get_all() -> QuerySet[Company]:
        return Company.objects.all().order_by("-created_at")

    @staticmethod
    def get_active() -> QuerySet[Company]:
        return Company.objects.filter(is_active=True)

    @staticmethod
    def get_by_id(*, company_id: int) -> Optional[Company]:
        return Company.objects.filter(id=company_id).first()

    @staticmethod
    def get_company_stats(*, company: Company) -> dict:
        """Get basic stats for a specific company."""
        order_count = Order.objects.filter(company=company).count()
        from apps.accounts.models import CompanyUser
        user_count = CompanyUser.objects.filter(company=company).count()
        return {
            "order_count": order_count,
            "user_count": user_count,
        }


class PlanSelector:
    """Read operations for Plans."""

    @staticmethod
    def get_all() -> QuerySet[Plan]:
        return Plan.objects.all()

    @staticmethod
    def get_active() -> QuerySet[Plan]:
        return Plan.objects.filter(is_active=True)

    @staticmethod
    def get_by_id(*, plan_id: int) -> Optional[Plan]:
        return Plan.objects.filter(id=plan_id).first()

    @staticmethod
    def get_by_code(*, code: str) -> Optional[Plan]:
        return Plan.objects.filter(code=code).first()


class SubscriptionSelector:
    """Read operations for Subscriptions."""

    @staticmethod
    def get_all() -> QuerySet[Subscription]:
        return Subscription.objects.select_related("company", "plan").all()

    @staticmethod
    def get_by_id(*, subscription_id: int) -> Optional[Subscription]:
        return Subscription.objects.select_related("company", "plan").filter(id=subscription_id).first()

    @staticmethod
    def get_for_company(*, company_id: int) -> Optional[Subscription]:
        return Subscription.objects.filter(company_id=company_id).first()
