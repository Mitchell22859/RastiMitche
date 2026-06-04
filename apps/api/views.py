"""
API - Views.

DRF API views for tenant and platform endpoints.
Views are THIN — they delegate to existing selectors/services.
No business logic duplication.

IMPORTANT: All tenant views use request.company for isolation.
"""
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import Customer, UserRole
from apps.invoices.selectors import InvoiceSelector
from apps.notifications.selectors import NotificationSelector
from apps.notifications.services import NotificationMarkReadService
from apps.orders.models import Order
from apps.orders.selectors import OrderSelector
from apps.orders.services import (
    OrderAcceptService,
    OrderCompleteService,
    OrderCreateService,
)
from apps.reports.selectors import CompanyReportSelector, PlatformReportSelector
from apps.tenants.models import CompanyService as CompanyServiceModel
from apps.tenants.selectors import CompanyServiceSelector, ServiceRequestSelector
from apps.tenants.services import ServiceRequestCreateService

from .permissions import IsPlatformOwner, IsTenantAdminOrStaff, IsTenantUser
from .serializers import (
    CompanySerializer,
    CompanyServiceSerializer,
    InvoiceSerializer,
    NotificationSerializer,
    OrderCreateSerializer,
    OrderSerializer,
    ServiceRequestCreateSerializer,
    ServiceRequestSerializer,
)


# =============================================================================
# TENANT API VIEWS
# =============================================================================


class OrderListAPI(APIView):
    """
    GET: List orders for the current tenant (role-filtered).
    POST: Create a new order (admin/staff only).
    """

    permission_classes = [IsTenantUser]

    def get(self, request, **kwargs):
        company = request.company
        user = request.user

        if user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
            orders = OrderSelector.get_for_company(company=company)
        elif user.role == UserRole.TECHNICIAN:
            technician = getattr(user, "technician_profile", None)
            orders = OrderSelector.get_for_technician(technician=technician) if technician else Order.objects.none()
        elif user.role == UserRole.CUSTOMER:
            customer = getattr(user, "customer_profile", None)
            orders = OrderSelector.get_for_customer(customer=customer) if customer else Order.objects.none()
        else:
            orders = Order.objects.none()

        serializer = OrderSerializer(orders, many=True)
        return Response(serializer.data)

    def post(self, request, **kwargs):
        if request.user.role not in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
            return Response({"error": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        serializer = OrderCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        company = request.company
        customer = Customer.objects.filter(
            id=serializer.validated_data["customer_id"], company=company
        ).first()

        if not customer:
            return Response({"error": "Customer not found."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = OrderCreateService.create(
                company=company,
                customer=customer,
                title=serializer.validated_data["title"],
                description=serializer.validated_data.get("description", ""),
                address=serializer.validated_data.get("address", ""),
                priority=serializer.validated_data.get("priority", Order.Priority.NORMAL),
                price_estimate=serializer.validated_data.get("price_estimate", 0),
                required_skill=serializer.validated_data.get("required_skill", ""),
                created_by=request.user,
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class OrderDetailAPI(APIView):
    """
    GET: Retrieve a single order.
    """

    permission_classes = [IsTenantUser]

    def get(self, request, order_id: int, **kwargs):
        company = request.company
        order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)
        if order is None:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        from apps.orders.permissions import can_view_order
        if not can_view_order(user=request.user, order=order):
            return Response({"error": "Access denied."}, status=status.HTTP_403_FORBIDDEN)

        return Response(OrderSerializer(order).data)


class InvoiceListAPI(APIView):
    """GET: List invoices for the current tenant (role-filtered)."""

    permission_classes = [IsTenantUser]

    def get(self, request, **kwargs):
        company = request.company
        user = request.user

        if user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
            invoices = InvoiceSelector.get_for_company(company=company)
        elif user.role == UserRole.CUSTOMER:
            customer = getattr(user, "customer_profile", None)
            invoices = InvoiceSelector.get_for_customer(customer=customer) if customer else []
        else:
            invoices = []

        serializer = InvoiceSerializer(invoices, many=True)
        return Response(serializer.data)


class NotificationListAPI(APIView):
    """GET: List notifications for the current user."""

    permission_classes = [IsTenantUser]

    def get(self, request, **kwargs):
        company = request.company
        notifications = NotificationSelector.get_for_user(
            company=company, user=request.user
        )
        serializer = NotificationSerializer(notifications, many=True)
        return Response(serializer.data)


class CompanyServiceListAPI(APIView):
    """GET: List active services for the company (public-friendly)."""

    permission_classes = [AllowAny]

    def get(self, request, **kwargs):
        company = getattr(request, "company", None)
        if not company:
            return Response({"error": "Company not found."}, status=status.HTTP_404_NOT_FOUND)

        services = CompanyServiceSelector.get_active_for_company(company=company)
        serializer = CompanyServiceSerializer(services, many=True)
        return Response(serializer.data)


class ServiceRequestListAPI(APIView):
    """
    GET: List service requests (admin only).
    POST: Create a service request (public, no auth required).
    """

    def get_permissions(self):
        if self.request.method == "POST":
            return [AllowAny()]
        return [IsTenantAdminOrStaff()]

    def get(self, request, **kwargs):
        company = request.company
        requests = ServiceRequestSelector.get_for_company(company=company)
        serializer = ServiceRequestSerializer(requests, many=True)
        return Response(serializer.data)

    def post(self, request, **kwargs):
        company = getattr(request, "company", None)
        if not company:
            return Response({"error": "Company not found."}, status=status.HTTP_404_NOT_FOUND)

        serializer = ServiceRequestCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        service = None
        service_id = serializer.validated_data.get("service_id")
        if service_id:
            service = CompanyServiceSelector.get_by_id_for_company(
                service_id=service_id, company=company
            )

        try:
            sr = ServiceRequestCreateService.create(
                company=company,
                customer_name=serializer.validated_data["customer_name"],
                customer_phone=serializer.validated_data["customer_phone"],
                customer_email=serializer.validated_data.get("customer_email", ""),
                address=serializer.validated_data.get("address", ""),
                service=service,
                description=serializer.validated_data.get("description", ""),
                preferred_time=serializer.validated_data.get("preferred_time", ""),
            )
        except ValueError as e:
            return Response({"error": str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(ServiceRequestSerializer(sr).data, status=status.HTTP_201_CREATED)


# =============================================================================
# PLATFORM API VIEWS
# =============================================================================


class PlatformCompanyListAPI(APIView):
    """GET: List all companies (platform owner only)."""

    permission_classes = [IsPlatformOwner]

    def get(self, request):
        from apps.tenants.models import Company
        companies = Company.objects.all()
        serializer = CompanySerializer(companies, many=True)
        return Response(serializer.data)


class PlatformReportsAPI(APIView):
    """GET: Platform-level reports (platform owner only)."""

    permission_classes = [IsPlatformOwner]

    def get(self, request):
        return Response({
            "company_summary": PlatformReportSelector.company_summary(),
            "subscription_summary": PlatformReportSelector.subscription_summary(),
        })


# =============================================================================
# EXTENDED TENANT API VIEWS
# =============================================================================


class CustomerListAPI(APIView):
    """
    GET: List customers for the current tenant.
    POST: Create a new customer.
    """

    permission_classes = [IsTenantAdminOrStaff]

    def get(self, request, **kwargs):
        company = request.company
        customers = Customer.objects.filter(company=company).order_by("-created_at")
        data = [
            {
                "id": c.id,
                "name": str(c),
                "phone": c.phone,
                "email": c.email,
                "address": c.address,
                "notes": c.notes,
                "total_orders": c.orders.count(),
                "created_at": c.created_at.isoformat(),
                "updated_at": c.updated_at.isoformat(),
            }
            for c in customers
        ]
        return Response(data)

    def post(self, request, **kwargs):
        company = request.company
        data = request.data

        # Validate required fields
        if not data.get("name") or not data.get("phone"):
            return Response(
                {"error": "Name and phone are required."},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Check if customer with same phone exists
        if Customer.objects.filter(company=company, phone=data["phone"]).exists():
            return Response(
                {"error": "Customer with this phone number already exists."},
                status=status.HTTP_400_BAD_REQUEST
            )

        customer = Customer.objects.create(
            company=company,
            name=data["name"],
            phone=data["phone"],
            email=data.get("email", ""),
            address=data.get("address", ""),
            notes=data.get("notes", ""),
        )

        return Response({
            "id": customer.id,
            "name": str(customer),
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "notes": customer.notes,
            "total_orders": 0,
            "created_at": customer.created_at.isoformat(),
            "updated_at": customer.updated_at.isoformat(),
        }, status=status.HTTP_201_CREATED)


class CustomerDetailAPI(APIView):
    """
    GET: Retrieve a single customer.
    PUT: Update a customer.
    DELETE: Delete a customer.
    """

    permission_classes = [IsTenantAdminOrStaff]

    def get(self, request, customer_id: int, **kwargs):
        company = request.company
        customer = Customer.objects.filter(company=company, id=customer_id).first()
        if not customer:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        return Response({
            "id": customer.id,
            "name": str(customer),
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "notes": customer.notes,
            "total_orders": customer.orders.count(),
            "created_at": customer.created_at.isoformat(),
            "updated_at": customer.updated_at.isoformat(),
        })

    def put(self, request, customer_id: int, **kwargs):
        company = request.company
        customer = Customer.objects.filter(company=company, id=customer_id).first()
        if not customer:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        data = request.data
        if data.get("name"):
            customer.name = data["name"]
        if "phone" in data:
            customer.phone = data["phone"]
        if "email" in data:
            customer.email = data["email"]
        if "address" in data:
            customer.address = data["address"]
        if "notes" in data:
            customer.notes = data["notes"]

        customer.save()

        return Response({
            "id": customer.id,
            "name": str(customer),
            "phone": customer.phone,
            "email": customer.email,
            "address": customer.address,
            "notes": customer.notes,
            "total_orders": customer.orders.count(),
            "created_at": customer.created_at.isoformat(),
            "updated_at": customer.updated_at.isoformat(),
        })

    def delete(self, request, customer_id: int, **kwargs):
        company = request.company
        customer = Customer.objects.filter(company=company, id=customer_id).first()
        if not customer:
            return Response({"error": "Not found."}, status=status.HTTP_404_NOT_FOUND)

        # Don't delete if customer has orders
        if customer.orders.exists():
            return Response(
                {"error": "Cannot delete customer with existing orders."},
                status=status.HTTP_400_BAD_REQUEST
            )

        customer.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class TechnicianListAPI(APIView):
    """GET: List technicians for the current tenant."""

    permission_classes = [IsTenantAdminOrStaff]

    def get(self, request, **kwargs):
        from apps.accounts.models import Technician

        company = request.company
        technicians = Technician.objects.filter(company=company).select_related("user")

        data = [
            {
                "id": t.id,
                "user": t.user_id,
                "user_name": t.user.get_full_name(),
                "user_phone": t.user.phone,
                "national_id": t.national_id,
                "is_available": t.is_available,
                "rating": float(t.rating),
                "notes": t.notes,
                "skills": [
                    {"id": s.id, "name": s.name, "level": s.level}
                    for s in t.skills.all()
                ],
                "created_at": t.created_at.isoformat(),
                "updated_at": t.updated_at.isoformat(),
            }
            for t in technicians
        ]
        return Response(data)


class DashboardAPI(APIView):
    """GET: Dashboard statistics for the current tenant."""

    permission_classes = [IsTenantUser]

    def get(self, request, **kwargs):
        from django.db.models import Sum, Count
        from django.utils import timezone
        from datetime import timedelta
        from apps.invoices.models import Invoice

        company = request.company
        today = timezone.now().date()
        month_start = today.replace(day=1)

        # Order stats
        total_orders = Order.objects.filter(company=company).count()
        orders_today = Order.objects.filter(
            company=company, created_at__date=today
        ).count()
        orders_in_progress = Order.objects.filter(
            company=company, status=Order.Status.IN_PROGRESS
        ).count()
        completed_orders = Order.objects.filter(
            company=company, status=Order.Status.DONE
        ).count()

        # Revenue stats
        total_revenue = Invoice.objects.filter(
            company=company, status=Invoice.Status.PAID
        ).aggregate(total=Sum("total_amount"))["total"] or 0

        revenue_this_month = Invoice.objects.filter(
            company=company,
            status=Invoice.Status.PAID,
            paid_at__date__gte=month_start
        ).aggregate(total=Sum("total_amount"))["total"] or 0

        # Customer & technician counts
        total_customers = Customer.objects.filter(company=company).count()
        from apps.accounts.models import Technician
        total_technicians = Technician.objects.filter(company=company).count()

        # Pending invoices
        pending_invoices = Invoice.objects.filter(
            company=company, status=Invoice.Status.ISSUED
        ).count()

        # New service requests
        from apps.tenants.models import ServiceRequest
        new_service_requests = ServiceRequest.objects.filter(
            company=company, order__isnull=True
        ).count()

        return Response({
            "total_orders": total_orders,
            "orders_today": orders_today,
            "orders_in_progress": orders_in_progress,
            "completed_orders": completed_orders,
            "total_revenue": total_revenue,
            "revenue_this_month": revenue_this_month,
            "total_customers": total_customers,
            "total_technicians": total_technicians,
            "pending_invoices": pending_invoices,
            "new_service_requests": new_service_requests,
        })
