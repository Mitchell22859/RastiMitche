"""
Reports - Selectors.

Reporting queries for company and platform analytics.
All company-level reports MUST filter by company.

IMPORTANT: Reports are read-only aggregation queries.
"""
from django.db.models import Count, Sum, Q
from django.utils import timezone

from apps.accounts.models import Technician
from apps.invoices.models import Invoice
from apps.orders.models import Order
from apps.tenants.models import Company, CompanyService, ServiceRequest


class CompanyReportSelector:
    """
    Reporting queries for a specific company.
    Used by COMPANY_ADMIN / COMPANY_STAFF.
    """

    @staticmethod
    def order_summary(*, company) -> dict:
        """Order count by status."""
        qs = Order.objects.filter(company=company)
        return {
            "total": qs.count(),
            "new": qs.filter(status=Order.Status.NEW).count(),
            "in_progress": qs.filter(status=Order.Status.IN_PROGRESS).count(),
            "done": qs.filter(status=Order.Status.DONE).count(),
            "cancelled": qs.filter(status=Order.Status.CANCELLED).count(),
            "cancel_requested": qs.filter(status=Order.Status.CANCEL_REQUESTED).count(),
        }

    @staticmethod
    def revenue_summary(*, company) -> dict:
        """Revenue from PAID invoices only."""
        paid_qs = Invoice.objects.filter(company=company, status=Invoice.Status.PAID)
        total_revenue = paid_qs.aggregate(total=Sum("total_amount"))["total"] or 0
        invoice_count = paid_qs.count()

        return {
            "total_revenue": total_revenue,
            "paid_invoice_count": invoice_count,
        }

    @staticmethod
    def invoice_summary(*, company) -> dict:
        """Invoice count by status."""
        qs = Invoice.objects.filter(company=company)
        return {
            "total": qs.count(),
            "draft": qs.filter(status=Invoice.Status.DRAFT).count(),
            "issued": qs.filter(status=Invoice.Status.ISSUED).count(),
            "paid": qs.filter(status=Invoice.Status.PAID).count(),
            "cancelled": qs.filter(status=Invoice.Status.CANCELLED).count(),
        }

    @staticmethod
    def technician_performance(*, company) -> list[dict]:
        """Technician performance: completed orders and active orders."""
        technicians = Technician.objects.filter(company=company)
        result = []
        for tech in technicians:
            completed = Order.objects.filter(
                company=company, technician=tech, status=Order.Status.DONE
            ).count()
            active = Order.objects.filter(
                company=company, technician=tech, status=Order.Status.IN_PROGRESS
            ).count()
            result.append({
                "technician": tech,
                "completed_orders": completed,
                "active_orders": active,
            })
        return result

    @staticmethod
    def service_request_summary(*, company) -> dict:
        """Summary of service requests."""
        total = ServiceRequest.objects.filter(company=company).count()
        return {"total_requests": total}


class PlatformReportSelector:
    """
    Reporting queries for PLATFORM_OWNER.
    Aggregates data across all companies.
    """

    @staticmethod
    def company_summary() -> dict:
        """Company count summary."""
        total = Company.objects.count()
        active = Company.objects.filter(is_active=True).count()
        inactive = Company.objects.filter(is_active=False).count()
        return {
            "total": total,
            "active": active,
            "inactive": inactive,
        }

    @staticmethod
    def subscription_summary() -> dict:
        """Subscription status summary."""
        from apps.platform_core.models import Subscription
        total = Subscription.objects.count()
        active = Subscription.objects.filter(status=Subscription.Status.ACTIVE).count()
        trial = Subscription.objects.filter(status=Subscription.Status.TRIAL).count()
        expired = Subscription.objects.filter(status=Subscription.Status.EXPIRED).count()
        return {
            "total": total,
            "active": active,
            "trial": trial,
            "expired": expired,
        }

    @staticmethod
    def tenant_usage_summary() -> list[dict]:
        """Usage stats per tenant."""
        companies = Company.objects.filter(is_active=True)
        result = []
        for company in companies:
            order_count = Order.objects.filter(company=company).count()
            result.append({
                "company": company,
                "order_count": order_count,
            })
        return result
