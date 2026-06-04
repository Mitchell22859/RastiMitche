"""
Orders - Selectors.

All read operations for orders. ALWAYS company-scoped.
No business queries should exist in views — only here.

IMPORTANT: Every query MUST filter by company.
"""
from typing import Optional

from django.conf import settings
from django.db.models import Count, Q, QuerySet

from apps.accounts.models import Customer, Technician, TechnicianSkill

from .models import Order, OrderItemDefinition, OrderStatusLog


# Maximum concurrent active orders per technician
TECHNICIAN_MAX_ACTIVE_ORDERS = getattr(settings, "TECHNICIAN_MAX_ACTIVE_ORDERS", 5)


class OrderSelector:
    """
    Read operations for Orders.
    All methods enforce company-level isolation.
    """

    # =========================================================================
    # ADMIN / STAFF SELECTORS
    # =========================================================================

    @staticmethod
    def get_for_company(*, company) -> QuerySet[Order]:
        """Get all orders for a company (admin view)."""
        return Order.objects.filter(company=company)

    @staticmethod
    def get_by_id_for_company(*, order_id: int, company) -> Optional[Order]:
        """Get a single order by ID, company-scoped."""
        return Order.objects.filter(id=order_id, company=company).first()

    @staticmethod
    def get_by_status(*, company, status: str) -> QuerySet[Order]:
        """Get orders filtered by status for a company."""
        return Order.objects.filter(company=company, status=status)

    # =========================================================================
    # CUSTOMER SELECTORS
    # =========================================================================

    @staticmethod
    def get_for_customer(*, customer: Customer) -> QuerySet[Order]:
        """
        Get orders for a specific customer.
        Customer can ONLY see their own orders.
        """
        return Order.objects.filter(
            company=customer.company,
            customer=customer,
        )

    # =========================================================================
    # TECHNICIAN SELECTORS
    # =========================================================================

    @staticmethod
    def get_for_technician(*, technician: Technician) -> QuerySet[Order]:
        """Get all orders assigned to a technician (past and current)."""
        return Order.objects.filter(
            company=technician.company,
            technician=technician,
        )

    @staticmethod
    def get_active_for_technician(*, technician: Technician) -> QuerySet[Order]:
        """
        Get active (in-progress) orders for a technician.
        Used to check workload limits.
        """
        return Order.objects.filter(
            company=technician.company,
            technician=technician,
            status=Order.Status.IN_PROGRESS,
        )

    @staticmethod
    def get_active_order_count(*, technician: Technician) -> int:
        """Count active orders for workload check."""
        return Order.objects.filter(
            company=technician.company,
            technician=technician,
            status=Order.Status.IN_PROGRESS,
        ).count()

    @staticmethod
    def get_visible_for_technician(*, technician: Technician) -> QuerySet[Order]:
        """
        Get orders visible to a technician for acceptance.

        Visibility rules:
        1. Same company as technician
        2. Status is NEW (not yet accepted)
        3. Technician is active (is_available=True)
        4. Technician has matching skill (if required_skill is set)
        5. Technician active order count < limit

        This is the CORE business logic for order matching.
        """
        if not technician.is_available:
            return Order.objects.none()

        # Check workload limit
        active_count = OrderSelector.get_active_order_count(technician=technician)
        if active_count >= TECHNICIAN_MAX_ACTIVE_ORDERS:
            return Order.objects.none()

        # Get technician's skill names
        technician_skills = set(
            TechnicianSkill.objects.filter(
                technician=technician
            ).values_list("name", flat=True)
        )

        # Base query: same company, NEW status
        qs = Order.objects.filter(
            company=technician.company,
            status=Order.Status.NEW,
        )

        # Filter by matching skill: orders with no required_skill OR
        # orders whose required_skill matches technician's skills
        if technician_skills:
            qs = qs.filter(
                Q(required_skill="") | Q(required_skill__in=technician_skills)
            )
        else:
            # Technician has no skills → only see orders with no skill requirement
            qs = qs.filter(required_skill="")

        return qs


class TechnicianOrderVisibilitySelector:
    """
    Phase 18b: Category-based technician order visibility with priority delays.

    This is the NEW visibility system based on:
    - TechnicianCategorySkill (priority 1/2/3)
    - CompanySettings (delay minutes, future order rules, max active orders)
    - Order.priority2_visible_at / priority3_visible_at timestamps

    The OLD get_visible_for_technician remains for backward compatibility
    with legacy name-based skill matching.
    """

    @staticmethod
    def get_active_order_count(*, technician: Technician) -> int:
        """
        Count technician's active orders.

        Active statuses: WAITING, IN_PROGRESS
        """
        return Order.objects.filter(
            company=technician.company,
            technician=technician,
            status__in=[Order.Status.WAITING, Order.Status.IN_PROGRESS],
        ).count()

    @staticmethod
    def get_available_orders(
        *,
        technician: Technician,
        now=None,
    ) -> QuerySet[Order]:
        """
        Get orders visible to a technician for acceptance using the
        category-based priority system.

        Visibility rules (all must pass):
        1. Same company as technician
        2. Order status == NEW
        3. Order.technician is NULL (unassigned)
        4. Order.service_category is set
        5. Technician is available (is_available=True)
        6. Technician has TechnicianCategorySkill for order.service_category
        7. Active order count < CompanySettings.max_active_orders_per_technician
        8. Priority-based time delay has passed
        9. Future order visibility rules pass

        Args:
            technician: The technician to check visibility for.
            now: Current datetime (injectable for testing). Defaults to timezone.now().

        Returns:
            QuerySet of visible Order objects.
        """
        from django.utils import timezone as tz
        from apps.accounts.models import TechnicianCategorySkill
        from apps.tenants.selectors import get_company_settings

        if now is None:
            now = tz.now()

        # Rule 5: technician must be available
        if not technician.is_available:
            return Order.objects.none()

        # Get company settings
        company = technician.company
        settings = get_company_settings(company)

        # Rule 7: workload limit
        active_count = TechnicianOrderVisibilitySelector.get_active_order_count(
            technician=technician,
        )
        if (
            settings.max_active_orders_per_technician > 0
            and active_count >= settings.max_active_orders_per_technician
        ):
            return Order.objects.none()

        # Get technician's category skills (category_id → priority)
        category_skills = dict(
            TechnicianCategorySkill.objects.filter(
                technician=technician,
            ).values_list("category_id", "priority")
        )

        if not category_skills:
            return Order.objects.none()

        # Rules 1-4: base queryset
        qs = Order.objects.filter(
            company=company,
            status=Order.Status.NEW,
            technician__isnull=True,
            service_category_id__in=category_skills.keys(),
        )

        # Rule 8: priority-based time filtering
        # Build Q objects for each priority level
        p1_categories = [
            cat_id for cat_id, pri in category_skills.items() if pri == 1
        ]
        p2_categories = [
            cat_id for cat_id, pri in category_skills.items() if pri == 2
        ]
        p3_categories = [
            cat_id for cat_id, pri in category_skills.items() if pri == 3
        ]

        priority_q = Q(pk__in=[])  # Start with empty (nothing matches)

        if p1_categories:
            # Priority 1: visible immediately
            priority_q = priority_q | Q(service_category_id__in=p1_categories)

        if p2_categories:
            # Priority 2: visible when now >= priority2_visible_at
            priority_q = priority_q | Q(
                service_category_id__in=p2_categories,
                priority2_visible_at__isnull=False,
                priority2_visible_at__lte=now,
            )

        if p3_categories:
            # Priority 3: visible when now >= priority3_visible_at
            priority_q = priority_q | Q(
                service_category_id__in=p3_categories,
                priority3_visible_at__isnull=False,
                priority3_visible_at__lte=now,
            )

        qs = qs.filter(priority_q)

        # Rule 9: future order visibility
        # Prefer Order.service_date (Jalali admin form stored as Gregorian DateField).
        # Fall back to scheduled_for for older/API-created orders.
        today = tz.localdate(now)
        future_q = (
            Q(service_date__isnull=False, service_date__lte=today)
            | Q(service_date__isnull=True, scheduled_for__isnull=True)
            | Q(service_date__isnull=True, scheduled_for__date__lte=today)
        )

        if settings.show_future_orders_to_technicians:
            if settings.future_orders_visible_after is not None:
                current_time = tz.localtime(now).time()
                if current_time >= settings.future_orders_visible_after:
                    future_q = future_q | Q(service_date__gt=today) | Q(
                        service_date__isnull=True, scheduled_for__date__gt=today
                    )
            else:
                future_q = future_q | Q(service_date__gt=today) | Q(
                    service_date__isnull=True, scheduled_for__date__gt=today
                )

        qs = qs.filter(future_q)

        return qs


class OrderStatusLogSelector:
    """Read operations for OrderStatusLog."""

    @staticmethod
    def get_for_order(*, order: Order) -> QuerySet[OrderStatusLog]:
        """Get status history for an order."""
        return OrderStatusLog.objects.filter(
            company=order.company,
            order=order,
        )


class OrderItemDefinitionSelector:
    """Read operations for OrderItemDefinition."""

    @staticmethod
    def get_active_for_company(*, company) -> QuerySet[OrderItemDefinition]:
        """Get all active item definitions for a company."""
        return OrderItemDefinition.objects.filter(company=company, is_active=True)

    @staticmethod
    def get_active_for_category(*, company, category) -> QuerySet[OrderItemDefinition]:
        """Get active item definitions for a specific category within a company."""
        return OrderItemDefinition.objects.filter(
            company=company, category=category, is_active=True,
        )

    @staticmethod
    def get_all_for_company(*, company) -> QuerySet[OrderItemDefinition]:
        """Get all item definitions for a company (admin view)."""
        return OrderItemDefinition.objects.filter(company=company)
