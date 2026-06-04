"""
Platform Core - Service Layer.

All write operations and business logic for platform-level resources.
"""
from typing import Any


class PlanService:
    """Service for managing subscription plans."""

    @staticmethod
    def create_plan(*, data: dict[str, Any]) -> Any:
        """Create a new subscription plan."""
        from .models import Plan

        plan = Plan(**data)
        plan.full_clean()
        plan.save()
        return plan

    @staticmethod
    def update_plan(*, plan_id: int, data: dict[str, Any]) -> Any:
        """Update an existing plan."""
        from .models import Plan

        plan = Plan.objects.get(id=plan_id)
        for key, value in data.items():
            setattr(plan, key, value)
        plan.full_clean()
        plan.save()
        return plan


class SubscriptionService:
    """Service for managing company subscriptions."""

    @staticmethod
    def create_subscription(*, data: dict[str, Any]) -> Any:
        """Create a subscription for a company."""
        from .models import Subscription

        subscription = Subscription(**data)
        subscription.full_clean()
        subscription.save()
        return subscription
