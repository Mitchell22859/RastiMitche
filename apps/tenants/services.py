"""
Tenants - Service Layer.

Write operations for company pages, services, gallery, and service requests.

IMPORTANT:
- ServiceRequestCreateService creates both a Customer (if new) and an Order.
- All operations enforce tenant isolation.
"""
from typing import Any, Optional

from django.db import transaction

from apps.accounts.models import Customer
from apps.orders.eligibility import set_missing_priority_visibility_times
from apps.orders.models import Order

from .models import (
    Company,
    CompanyGalleryImage,
    CompanyPage,
    CompanyService,
    ServiceRequest,
)


class CompanyPageUpdateService:
    """Service for updating company public page settings."""

    @staticmethod
    def update(*, company: Company, data: dict[str, Any]) -> CompanyPage:
        """
        Update the company's public page.

        Creates the page if it doesn't exist.
        """
        page, _ = CompanyPage.objects.get_or_create(company=company)
        for key, value in data.items():
            if hasattr(page, key):
                setattr(page, key, value)
        page.save()
        return page


class CompanyServiceCreateService:
    """Service for creating company services."""

    @staticmethod
    def create(*, company: Company, data: dict[str, Any]) -> CompanyService:
        """Create a new service for a company."""
        service = CompanyService(company=company, **data)
        service.full_clean()
        service.save()
        return service


class CompanyServiceUpdateService:
    """Service for updating company services."""

    @staticmethod
    def update(*, service: CompanyService, data: dict[str, Any]) -> CompanyService:
        """Update an existing service."""
        for key, value in data.items():
            if hasattr(service, key):
                setattr(service, key, value)
        service.full_clean()
        service.save()
        return service


class GalleryImageCreateService:
    """Service for managing gallery images."""

    @staticmethod
    def create(*, company: Company, **kwargs) -> CompanyGalleryImage:
        """Create a gallery image."""
        image = CompanyGalleryImage(company=company, **kwargs)
        image.full_clean()
        image.save()
        return image


class ServiceRequestCreateService:
    """
    Service for handling public service request submissions.

    Flow:
    1. Find or create Customer by phone within the company.
    2. Create an Order with status NEW.
    3. Create the ServiceRequest linking to the Order.

    IMPORTANT:
    - All records are created under request.company (tenant isolation).
    - Customer is matched by phone within the same company.
    """

    @staticmethod
    @transaction.atomic
    def create(
        *,
        company: Company,
        customer_name: str,
        customer_phone: str,
        customer_email: str = "",
        address: str = "",
        service: Optional[CompanyService] = None,
        description: str = "",
        preferred_time: str = "",
        service_category_id: Optional[int] = None,
    ) -> ServiceRequest:
        """
        Create a service request from a public form submission.

        Args:
            company: The tenant company (from request.company).
            customer_name: Visitor's name.
            customer_phone: Visitor's phone (used to match/create Customer).
            customer_email: Optional email.
            address: Service address.
            service: Optional CompanyService selected.
            description: Problem description.
            preferred_time: Preferred time string.
            service_category_id: Optional service category for dynamic items.

        Returns:
            Created ServiceRequest instance (with linked Order).
        """
        # Validate service belongs to same company
        if service and service.company_id != company.id:
            raise ValueError("Service does not belong to this company.")

        # Step 1: Find or create Customer
        customer = ServiceRequestCreateService._get_or_create_customer(
            company=company,
            name=customer_name,
            phone=customer_phone,
            email=customer_email,
            address=address,
        )

        # Step 2: Resolve service category
        service_category = None
        if service_category_id:
            from .models import CompanyServiceCategory
            service_category = CompanyServiceCategory.objects.filter(
                id=service_category_id, company=company, is_active=True,
            ).first()

        # Step 3: Create Order
        order_title = service.title if service else "Service Request"
        price_estimate = int(service.base_price) if service else 0

        order = Order(
            company=company,
            customer=customer,
            title=order_title,
            description=description,
            address=address,
            status=Order.Status.NEW,
            price_estimate=price_estimate,
            required_skill="",
            service_category=service_category,
        )
        set_missing_priority_visibility_times(order=order)
        order.full_clean()
        order.save()

        # Step 4: Create ServiceRequest
        request = ServiceRequest.objects.create(
            company=company,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            address=address,
            service=service,
            description=description,
            preferred_time=preferred_time,
            order=order,
        )

        from apps.orders.order_events import dispatch_order_available_events
        dispatch_order_available_events(order=order)

        return request

    @staticmethod
    def _get_or_create_customer(
        *, company: Company, name: str, phone: str, email: str, address: str
    ) -> Customer:
        """
        Find existing customer by phone within the company,
        or create a new one.
        """
        customer = Customer.objects.filter(
            company=company, phone=phone
        ).first()

        if customer is None:
            # Split name into first/last
            parts = name.strip().split(" ", 1)
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

            customer = Customer.objects.create(
                company=company,
                first_name=first_name,
                last_name=last_name,
                phone=phone,
                email=email,
                address=address,
            )

        return customer
