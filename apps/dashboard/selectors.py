"""
Dashboard - Selectors.

Aggregation queries for dashboard widgets.
Each selector is role-scoped to prevent cross-tenant leaks.

IMPORTANT: All tenant-level queries MUST filter by company.
"""
from django.db.models import Count, Sum, Q
from django.utils import timezone

from apps.accounts.models import Customer, Technician
from apps.invoices.models import Invoice
from apps.orders.models import Order
from apps.orders.selectors import OrderSelector
from apps.tenants.models import Company, ServiceRequest


class PlatformDashboardSelector:
    """
    Dashboard data for PLATFORM_OWNER.
    Shows global platform statistics.
    NOT tenant-scoped — shows data across all companies.
    """

    @staticmethod
    def get_stats() -> dict:
        """Get platform-level statistics."""
        total = Company.objects.count()
        active = Company.objects.filter(is_active=True).count()
        inactive = Company.objects.filter(is_active=False).count()

        from apps.platform_core.models import Subscription
        subscription_count = Subscription.objects.count()

        return {
            "total_companies": total,
            "active_companies": active,
            "inactive_companies": inactive,
            "subscription_count": subscription_count,
        }

    @staticmethod
    def get_recent_companies(*, limit: int = 10):
        """Get recently created companies."""
        return Company.objects.order_by("-created_at")[:limit]


class CompanyDashboardSelector:
    """
    Dashboard data for COMPANY_ADMIN / COMPANY_STAFF.
    Shows statistics for ONE company only.
    """

    @staticmethod
    def get_stats(*, company) -> dict:
        """Get company-level dashboard statistics."""
        today = timezone.now().date()

        orders_qs = Order.objects.filter(company=company)
        invoices_qs = Invoice.objects.filter(company=company)

        today_orders = orders_qs.filter(created_at__date=today).count()
        new_orders = orders_qs.filter(status=Order.Status.NEW).count()
        in_progress_orders = orders_qs.filter(status=Order.Status.IN_PROGRESS).count()
        done_orders = orders_qs.filter(status=Order.Status.DONE).count()

        unpaid_invoices = invoices_qs.filter(status=Invoice.Status.ISSUED).count()
        paid_invoices = invoices_qs.filter(status=Invoice.Status.PAID).count()

        total_revenue = invoices_qs.filter(
            status=Invoice.Status.PAID
        ).aggregate(total=Sum("total_amount"))["total"] or 0

        active_technicians = Technician.objects.filter(
            company=company, is_available=True
        ).count()

        return {
            "today_orders": today_orders,
            "new_orders": new_orders,
            "in_progress_orders": in_progress_orders,
            "done_orders": done_orders,
            "unpaid_invoices": unpaid_invoices,
            "paid_invoices": paid_invoices,
            "total_revenue": total_revenue,
            "active_technicians": active_technicians,
        }

    @staticmethod
    def get_recent_orders(*, company, limit: int = 10):
        """Get recent orders for the company."""
        return Order.objects.filter(company=company).order_by("-created_at")[:limit]


class TechnicianDashboardSelector:
    """
    Dashboard data for TECHNICIAN.
    Shows only the technician's own data.
    """

    @staticmethod
    def get_stats(*, technician: Technician) -> dict:
        """Get technician-specific statistics."""
        from apps.orders.selectors import TechnicianOrderVisibilitySelector
        from apps.orders.eligibility import is_order_accept_allowed_by_service_date

        visible = TechnicianOrderVisibilitySelector.get_available_orders(
            technician=technician,
        )
        # Count only orders that are currently acceptable (not future-gated)
        acceptable_count = sum(
            1 for order in visible[:100]
            if is_order_accept_allowed_by_service_date(order=order)
        )
        waiting = Order.objects.filter(
            company=technician.company,
            technician=technician,
            status=Order.Status.WAITING,
        )
        in_progress = Order.objects.filter(
            company=technician.company,
            technician=technician,
            status=Order.Status.IN_PROGRESS,
        )
        completed = Order.objects.filter(
            company=technician.company,
            technician=technician,
            status=Order.Status.DONE,
        )

        return {
            "visible_orders": acceptable_count,
            "waiting_orders": waiting.count(),
            "in_progress_orders": in_progress.count(),
            "active_orders": waiting.count() + in_progress.count(),
            "completed_orders": completed.count(),
        }

    @staticmethod
    def get_recent_assigned(*, technician: Technician, limit: int = 10):
        """Get recent orders assigned to this technician."""
        return Order.objects.filter(
            company=technician.company,
            technician=technician,
        ).order_by("-created_at")[:limit]


class CustomerDashboardSelector:
    """
    Dashboard data for CUSTOMER.
    Shows only the customer's own data.
    """

    @staticmethod
    def get_stats(*, customer: Customer) -> dict:
        """Get customer-specific statistics."""
        orders_qs = Order.objects.filter(
            company=customer.company, customer=customer
        )
        invoices_qs = Invoice.objects.filter(
            company=customer.company, customer=customer
        )

        return {
            "total_orders": orders_qs.count(),
            "unpaid_invoices": invoices_qs.filter(status=Invoice.Status.ISSUED).count(),
            "paid_invoices": invoices_qs.filter(status=Invoice.Status.PAID).count(),
        }

    @staticmethod
    def get_recent_orders(*, customer: Customer, limit: int = 10):
        """Get recent orders for this customer."""
        return Order.objects.filter(
            company=customer.company, customer=customer
        ).order_by("-created_at")[:limit]
