"""
Orders - Service Layer.

All write operations and business logic for the order engine.
Services are the ONLY place where order state transitions happen.

IMPORTANT:
- Services handle business rules enforcement
- Services create audit logs (OrderStatusLog)
- Services use transactions for data integrity
- Services never handle HTTP request/response
"""
from decimal import Decimal
from typing import Any, Optional

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CompanyUser, Customer, Technician

from .eligibility import set_missing_priority_visibility_times
from .models import Order, OrderStatusLog
from .selectors import OrderSelector, TECHNICIAN_MAX_ACTIVE_ORDERS


class OrderCreateService:
    """
    Service for creating new orders.

    Rules:
    - Order must belong to a company (enforced by CompanyOwnedModel)
    - Customer must belong to the same company
    - Initial status is always NEW
    """

    @staticmethod
    @transaction.atomic
    def create(
        *,
        company,
        customer: Customer,
        title: str,
        description: str = "",
        address: str = "",
        scheduled_for=None,
        priority: str = Order.Priority.NORMAL,
        price_estimate: int = 0,
        required_skill: str = "",
        notes: str = "",
        created_by: Optional[CompanyUser] = None,
        customer_name: str = "",
        customer_phone: str = "",
        service_date=None,
        extra_payment=0,
        wage_deduction=0,
    ) -> Order:
        """
        Create a new service order.

        Args:
            company: The tenant company.
            customer: Customer requesting the service.
            title: Order title/summary.
            description: Detailed description.
            address: Service address.
            scheduled_for: Optional scheduled datetime.
            priority: Order priority level.
            price_estimate: Estimated price.
            required_skill: Required technician skill name.
            notes: Internal notes.
            created_by: User who created the order.

        Returns:
            Created Order instance.

        Raises:
            ValueError: If customer doesn't belong to the company.
        """
        # Enforce tenant isolation
        if customer.company_id != company.id:
            raise ValueError("Customer does not belong to this company.")

        order = Order(
            company=company,
            customer=customer,
            title=title,
            description=description,
            customer_name=(customer_name or f"{customer.first_name} {customer.last_name}".strip()),
            customer_phone=(customer_phone or customer.phone),
            address=address,
            service_date=service_date,
            scheduled_for=scheduled_for,
            status=Order.Status.NEW,
            priority=priority,
            price_estimate=price_estimate,
            extra_payment=extra_payment or 0,
            wage_deduction=wage_deduction or 0,
            required_skill=required_skill,
            notes=notes,
        )
        set_missing_priority_visibility_times(order=order)
        order.full_clean()
        order.save()

        # Create initial status log
        OrderStatusLog.objects.create(
            company=company,
            order=order,
            old_status="",
            new_status=Order.Status.NEW,
            changed_by=created_by,
            note="Order created.",
        )

        _emit_order_notification_event("order_created_admin", order, created_by)
        _emit_order_notification_event("order_created_customer", order, created_by)

        from .order_events import dispatch_order_available_events
        dispatch_order_available_events(order=order)

        return order


class OrderAcceptService:
    """
    Service for technician accepting an order.

    Rules:
    - Technician must belong to the same company
    - Technician must be active/available
    - Technician must have matching skill (if required)
    - Technician active order count must be below limit
    - Order must be in NEW status
    - Accepting locks the order from other technicians
    """

    @staticmethod
    @transaction.atomic
    def accept(
        *,
        order: Order,
        technician: Technician,
        accepted_by: CompanyUser,
    ) -> Order:
        """
        Technician accepts an order.

        Transitions: NEW → IN_PROGRESS
        Assigns technician and creates audit log.

        Args:
            order: The order to accept.
            technician: The technician accepting.
            accepted_by: The user performing the action.

        Returns:
            Updated Order instance.

        Raises:
            ValueError: If business rules are violated.
        """
        # Rule: same company
        if order.company_id != technician.company_id:
            raise ValueError("Technician does not belong to this company.")

        # Rule: order must be NEW
        if order.status != Order.Status.NEW:
            raise ValueError("Order is not available for acceptance.")

        # Re-fetch with lock to prevent race conditions
        locked_order = Order.objects.select_for_update().get(pk=order.pk)
        if locked_order.status != Order.Status.NEW:
            raise ValueError("Order is not available for acceptance.")

        # Use the locked instance for updates
        order = locked_order

        # Rule: technician must be available
        if not technician.is_available:
            raise ValueError("Technician is not available.")

        # Rule: workload limit
        active_count = OrderSelector.get_active_order_count(technician=technician)
        if active_count >= TECHNICIAN_MAX_ACTIVE_ORDERS:
            raise ValueError("Technician has reached maximum active orders.")

        # Rule: skill matching (if required_skill is set)
        if order.required_skill:
            from apps.accounts.models import TechnicianSkill
            has_skill = TechnicianSkill.objects.filter(
                technician=technician,
                name=order.required_skill,
            ).exists()
            if not has_skill:
                raise ValueError("Technician does not have the required skill.")

        # Perform the transition
        old_status = order.status
        order.technician = technician
        order.status = Order.Status.IN_PROGRESS
        order.save(update_fields=["technician", "status", "updated_at"])

        # Create audit log
        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=Order.Status.IN_PROGRESS,
            changed_by=accepted_by,
            note=f"Accepted by technician: {technician.user.get_full_name()}",
        )

        _emit_order_notification_event("order_accepted_customer", order, accepted_by)

        return order


class OrderCompleteService:
    """
    Service for completing an order.

    Rules:
    - Only the assigned technician (or admin) can complete
    - Order must be IN_PROGRESS
    - Creates an invoice placeholder
    """

    @staticmethod
    @transaction.atomic
    def complete(
        *,
        order: Order,
        completed_by: CompanyUser,
        final_price: Optional[int] = None,
    ) -> Order:
        """
        Mark an order as completed (DONE).

        Transitions: IN_PROGRESS → DONE
        Creates invoice placeholder.

        Args:
            order: The order to complete.
            completed_by: User performing the action.
            final_price: Optional final price (overrides estimate).

        Returns:
            Updated Order instance.

        Raises:
            ValueError: If order is not in IN_PROGRESS status.
        """
        if order.status != Order.Status.IN_PROGRESS:
            raise ValueError("Order must be in progress to complete.")

        # Update order
        old_status = order.status
        order.status = Order.Status.DONE
        order.completed_at = timezone.now()
        if final_price is not None:
            order.final_price = final_price
        elif order.final_price == 0:
            order.final_price = order.price_estimate

        order.save(update_fields=[
            "status", "completed_at", "final_price", "updated_at"
        ])

        # Create audit log
        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=Order.Status.DONE,
            changed_by=completed_by,
            note="Order completed.",
        )

        # Create invoice placeholder
        OrderCompleteService._create_invoice_placeholder(order=order)

        _emit_order_notification_event("order_completed_customer", order, completed_by)

        # Emit survey request event (respects all existing SMS/notification rules)
        _emit_order_notification_event(
            "survey_request_customer", order, completed_by,
            dedup_extra="survey",
        )

        return order

    @staticmethod
    def _create_invoice_placeholder(*, order: Order) -> None:
        """
        Create a draft invoice for the completed order, unless one already exists.
        Uses InvoiceCreateService for proper invoice generation.
        Skips creation if a non-cancelled invoice already exists for this order.
        """
        from apps.invoices.services import InvoiceDuplicateGuard, InvoiceCreateService

        if InvoiceDuplicateGuard.has_active_for_order(company=order.company, order=order):
            return

        InvoiceCreateService.create_from_order(order=order)


class OrderCancelService:
    """
    Service for cancelling orders.

    Supports two flows:
    1. Cancel request (customer/technician) → admin approves
    2. Force cancel (admin directly)
    """

    @staticmethod
    @transaction.atomic
    def request_cancel(
        *,
        order: Order,
        requested_by: CompanyUser,
        reason: str = "",
    ) -> Order:
        """
        Request order cancellation.

        Transitions: NEW/IN_PROGRESS → CANCEL_REQUESTED

        Args:
            order: The order to cancel.
            requested_by: User requesting cancellation.
            reason: Reason for cancellation.

        Returns:
            Updated Order instance.

        Raises:
            ValueError: If order cannot be cancelled.
        """
        allowed_statuses = [Order.Status.NEW, Order.Status.IN_PROGRESS]
        if order.status not in allowed_statuses:
            raise ValueError("Order cannot be cancelled in its current status.")

        old_status = order.status
        order.status = Order.Status.CANCEL_REQUESTED
        order.save(update_fields=["status", "updated_at"])

        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=Order.Status.CANCEL_REQUESTED,
            changed_by=requested_by,
            note=f"Cancel requested. Reason: {reason}",
        )

        _emit_order_notification_event(
            "order_cancel_requested_customer",
            order,
            requested_by,
            payload={"reason": reason or ""},
        )

        return order

    @staticmethod
    @transaction.atomic
    def force_cancel(
        *,
        order: Order,
        cancelled_by: CompanyUser,
        reason: str = "",
    ) -> Order:
        """
        Force cancel an order (admin action).

        Transitions: Any non-terminal status → CANCELLED

        Args:
            order: The order to cancel.
            cancelled_by: Admin user performing the action.
            reason: Reason for cancellation.

        Returns:
            Updated Order instance.

        Raises:
            ValueError: If order is already done or cancelled.
        """
        terminal_statuses = [Order.Status.DONE, Order.Status.CANCELLED]
        if order.status in terminal_statuses:
            raise ValueError("Order is already in a terminal status.")

        old_status = order.status
        order.status = Order.Status.CANCELLED
        order.technician = None  # Release technician
        order.save(update_fields=["status", "technician", "updated_at"])

        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=Order.Status.CANCELLED,
            changed_by=cancelled_by,
            note=f"Force cancelled by admin. Reason: {reason}",
        )

        _emit_order_notification_event(
            "order_cancelled",
            order,
            cancelled_by,
            payload={"reason": reason or ""},
        )

        return order



class OrderUpdateService:
    """
    Service for editing order details by admin/staff.

    Rules:
    - Only admin/staff of the same company can edit.
    - Customer and technician cannot edit.
    - Creates a status log entry noting the edit.
    """

    @staticmethod
    @transaction.atomic
    def update(
        *,
        order: Order,
        updated_by: CompanyUser,
        data: dict,
    ) -> Order:
        """
        Update editable order fields.

        Args:
            order: The order to update.
            updated_by: User performing the edit.
            data: Dict of field→value to update.

        Returns:
            Updated Order instance.
        """
        editable_fields = [
            "title", "description", "address", "service_date", "scheduled_for",
            "customer_name", "customer_phone",
            "extra_payment", "wage_deduction",
            "required_skill", "price_estimate", "final_price",
            "internal_note", "notes",
        ]

        # Update customer if provided
        if "customer_id" in data and data["customer_id"]:
            from apps.accounts.models import Customer
            customer = Customer.objects.filter(
                id=data["customer_id"], company=order.company
            ).first()
            if customer:
                order.customer = customer

        # Update service category/subcategory if provided
        if "service_category_id" in data:
            cat_id = data["service_category_id"]
            if cat_id:
                from apps.tenants.models import CompanyServiceCategory
                cat = CompanyServiceCategory.objects.filter(id=cat_id, company=order.company).first()
                order.service_category = cat
            else:
                order.service_category = None
            update_fields = ["updated_at", "service_category_id"]
        else:
            update_fields = ["updated_at"]

        if "service_subcategory_id" in data:
            subcat_id = data["service_subcategory_id"]
            if subcat_id:
                from apps.tenants.models import CompanyServiceSubCategory
                subcat = CompanyServiceSubCategory.objects.filter(id=subcat_id, company=order.company).first()
                order.service_subcategory = subcat
            else:
                order.service_subcategory = None
            update_fields.append("service_subcategory_id")

        for field in editable_fields:
            if field in data:
                value = data[field]
                if value is None and field in {"scheduled_for", "service_date"}:
                    setattr(order, field, None)
                else:
                    setattr(order, field, value if value is not None else "")
                update_fields.append(field)

        if "customer_id" in data:
            update_fields.append("customer_id")

        old_status = order.status
        if "status" in data and data["status"]:
            valid_statuses = {choice[0] for choice in Order.Status.choices}
            if data["status"] not in valid_statuses:
                raise ValueError("وضعیت سفارش معتبر نیست.")
            order.status = data["status"]
            update_fields.append("status")

        # Avoid duplicate update fields.
        update_fields = list(dict.fromkeys(update_fields))
        order.save(update_fields=update_fields)

        # Log the edit/status update.
        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=order.status,
            changed_by=updated_by,
            note="Order details edited by admin.",
        )

        return order


class OrderAssignService:
    """
    Service for admin manual assignment of a technician.

    Different from OrderAcceptService (technician self-accept):
    - This is triggered by admin/staff.
    - Transitions: NEW → WAITING.
    - Validates technician belongs to same company, is active.
    """

    @staticmethod
    @transaction.atomic
    def assign(
        *,
        order: Order,
        technician: Technician,
        assigned_by: CompanyUser,
    ) -> Order:
        """
        Manually assign a technician to an order.

        Args:
            order: The order to assign.
            technician: The technician to assign.
            assigned_by: Admin/staff performing the action.

        Returns:
            Updated Order instance.

        Raises:
            ValueError: If validation fails.
        """
        if order.company_id != technician.company_id:
            raise ValueError("Technician does not belong to this company.")

        if order.status != Order.Status.NEW:
            raise ValueError("Only NEW orders can be assigned.")

        if not technician.is_available:
            raise ValueError("Technician is not active/available.")

        old_status = order.status
        order.technician = technician
        order.status = Order.Status.WAITING
        order.accepted_at = timezone.now()
        order.save(update_fields=["technician", "status", "accepted_at", "updated_at"])

        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=Order.Status.WAITING,
            changed_by=assigned_by,
            note=f"Manually assigned to {technician.user.get_full_name()} by admin.",
        )

        from .assignment_events import dispatch_order_assigned_events
        dispatch_order_assigned_events(order=order, technician=technician)

        return order



class OrderCreateByAdminService:
    """
    Service for admin/staff to create orders manually.

    Differences from OrderCreateService:
    - Supports service_category and service_subcategory
    - Supports optional technician assignment at creation
    - Supports quick customer creation by name+phone
    - Creates internal_note
    """

    @staticmethod
    @transaction.atomic
    def create(
        *,
        company,
        created_by: CompanyUser,
        title: str,
        customer: Optional[Customer] = None,
        customer_name: str = "",
        customer_phone: str = "",
        description: str = "",
        address: str = "",
        service_date=None,
        scheduled_for=None,
        priority: str = Order.Priority.NORMAL,
        price_estimate: int = 0,
        extra_payment=0,
        wage_deduction=0,
        required_skill: str = "",
        internal_note: str = "",
        status: str = Order.Status.NEW,
        service_category_id: Optional[int] = None,
        service_subcategory_id: Optional[int] = None,
        technician_id: Optional[int] = None,
    ) -> Order:
        """
        Create an order from admin panel.

        If customer is not provided, admin can enter free customer details.
        The service first tries to find an existing company customer by phone,
        otherwise it creates a lightweight customer record from name/phone.

        Returns:
            Created Order instance.

        Raises:
            ValueError: If validation fails.
        """
        # Resolve or create customer.
        # Admin order creation must not require selecting an existing customer.
        # A free name/phone pair is enough to create/reuse a company customer.
        customer_name = (customer_name or "").strip()
        customer_phone = (customer_phone or "").strip()
        address = (address or "").strip()

        if customer is not None and customer.company_id != company.id:
            raise ValueError("Customer does not belong to this company.")

        if customer is None:
            if not customer_name:
                raise ValueError("نام مشتری الزامی است.")
            if not customer_phone:
                raise ValueError("شماره تلفن مشتری الزامی است.")

            customer = Customer.objects.filter(
                company=company, phone=customer_phone
            ).first()

            if customer is None:
                parts = customer_name.split(" ", 1)
                first_name = parts[0]
                last_name = parts[1] if len(parts) > 1 else ""
                customer = Customer.objects.create(
                    company=company,
                    first_name=first_name,
                    last_name=last_name,
                    phone=customer_phone,
                    address=address,
                )
            else:
                # Keep existing customer identity, but improve empty profile fields
                # from the admin's free-input order form. Do not overwrite
                # non-empty profile data because an order address can be temporary.
                changed_fields = []
                if customer_name and not customer.first_name:
                    parts = customer_name.split(" ", 1)
                    customer.first_name = parts[0]
                    customer.last_name = parts[1] if len(parts) > 1 else ""
                    changed_fields.extend(["first_name", "last_name"])
                if address and not customer.address:
                    customer.address = address
                    changed_fields.append("address")
                if changed_fields:
                    customer.save(update_fields=changed_fields + ["updated_at"])

        if not address and customer.address:
            address = customer.address

        # Resolve category/subcategory
        service_category = None
        service_subcategory = None
        if service_category_id:
            from apps.tenants.models import CompanyServiceCategory
            service_category = CompanyServiceCategory.objects.filter(
                id=service_category_id, company=company
            ).first()

        if service_subcategory_id:
            from apps.tenants.models import CompanyServiceSubCategory
            service_subcategory = CompanyServiceSubCategory.objects.filter(
                id=service_subcategory_id, company=company
            ).first()
            # Validate subcategory belongs to selected category
            if service_subcategory and service_category:
                if service_subcategory.category_id != service_category.id:
                    raise ValueError("Subcategory does not belong to selected category.")

        # Resolve technician
        technician = None
        if technician_id:
            technician = Technician.objects.filter(
                id=technician_id, company=company, is_available=True
            ).first()

        if not title:
            title_parts = []
            if service_category:
                title_parts.append(service_category.title)
            if customer_name:
                title_parts.append(customer_name)
            title = " - ".join(title_parts) or "سفارش جدید"

        valid_statuses = {choice[0] for choice in Order.Status.choices}
        if status not in valid_statuses:
            status = Order.Status.NEW

        # Create order
        order = Order(
            company=company,
            customer=customer,
            customer_name=customer_name,
            customer_phone=customer_phone or (customer.phone if customer else ""),
            title=title,
            description=description,
            address=address,
            service_date=service_date,
            scheduled_for=scheduled_for,
            status=status,
            priority=priority,
            price_estimate=price_estimate,
            extra_payment=extra_payment or 0,
            wage_deduction=wage_deduction or 0,
            required_skill=required_skill,
            internal_note=internal_note,
            service_category=service_category,
            service_subcategory=service_subcategory,
        )

        # Priority visibility timestamps are calculated while the order is still NEW.
        # If a technician is assigned below, the fields are harmless historical data.
        set_missing_priority_visibility_times(order=order)

        # If admin directly assigns a technician, the order immediately enters WAITING.
        if technician:
            order.technician = technician
            order.status = Order.Status.WAITING
            order.accepted_at = timezone.now()

        order.full_clean()
        order.save()

        # Status log
        OrderStatusLog.objects.create(
            company=company,
            order=order,
            old_status="",
            new_status=order.status,
            changed_by=created_by,
            note="Order created by admin." + (
                f" Assigned to {technician.user.get_full_name()}." if technician else ""
            ),
        )

        _emit_order_notification_event("order_created_admin", order, created_by)
        _emit_order_notification_event("order_created_customer", order, created_by)

        if technician:
            from .assignment_events import dispatch_order_assigned_events
            dispatch_order_assigned_events(order=order, technician=technician)
        else:
            from .order_events import dispatch_order_available_events
            dispatch_order_available_events(order=order)

        return order



class TechnicianAcceptService:
    """
    Phase 18c: Safe technician accept with category-based visibility rules.

    Uses TechnicianOrderVisibilitySelector logic for eligibility checks
    inside a database transaction with row locking.

    Differences from OrderAcceptService:
    - Uses TechnicianCategorySkill (not TechnicianSkill) for eligibility
    - Uses CompanySettings.max_active_orders_per_technician
    - Counts WAITING + IN_PROGRESS as active orders
    - Enforces priority-based time delays
    - Enforces future order visibility rules
    - Sets status to WAITING (not IN_PROGRESS)
    - Sets accepted_at timestamp
    - Checks order.technician is NULL (unassigned)
    """

    @staticmethod
    @transaction.atomic
    def accept(
        *,
        order: Order,
        technician: "Technician",
        accepted_by: "CompanyUser",
        now=None,
    ) -> Order:
        """
        Technician accepts an order using category-based priority system.

        Transitions: NEW → WAITING
        Assigns technician, sets accepted_at, creates audit log.

        Args:
            order: The order to accept (will be re-fetched with lock).
            technician: The technician accepting.
            accepted_by: The user performing the action.
            now: Current datetime (injectable for testing).

        Returns:
            Updated Order instance.

        Raises:
            ValueError: If any eligibility rule fails.
        """
        from apps.accounts.models import TechnicianCategorySkill
        from apps.tenants.selectors import get_company_settings
        from .selectors import TechnicianOrderVisibilitySelector

        if now is None:
            now = timezone.now()

        # Pre-lock validation
        if order.company_id != technician.company_id:
            raise ValueError("Technician does not belong to this company.")

        # Lock the order row to prevent race conditions
        locked_order = Order.objects.select_for_update().get(pk=order.pk)

        # Rule: order must be NEW
        if locked_order.status != Order.Status.NEW:
            raise ValueError("Order is not available for acceptance.")

        # Rule: order must be unassigned
        if locked_order.technician_id is not None:
            raise ValueError("Order is already assigned to another technician.")

        # Rule: order must have a service_category
        if locked_order.service_category_id is None:
            raise ValueError("Order has no service category set.")

        # Rule: technician must be available
        if not technician.is_available:
            raise ValueError("Technician is not available.")

        # Rule: technician must have category skill
        category_skill = TechnicianCategorySkill.objects.filter(
            technician=technician,
            category_id=locked_order.service_category_id,
        ).first()
        if category_skill is None:
            raise ValueError(
                "Technician does not have the required category skill."
            )

        # Rule: workload limit from CompanySettings
        company_settings = get_company_settings(locked_order.company)
        active_count = TechnicianOrderVisibilitySelector.get_active_order_count(
            technician=technician,
        )
        if (
            company_settings.max_active_orders_per_technician > 0
            and active_count >= company_settings.max_active_orders_per_technician
        ):
            raise ValueError("Technician has reached maximum active orders.")

        # Rule: priority-based time delay
        priority = category_skill.priority
        if priority == 2:
            if (
                locked_order.priority2_visible_at is None
                or locked_order.priority2_visible_at > now
            ):
                raise ValueError(
                    "Order is not yet visible to priority-2 technicians."
                )
        elif priority == 3:
            if (
                locked_order.priority3_visible_at is None
                or locked_order.priority3_visible_at > now
            ):
                raise ValueError(
                    "Order is not yet visible to priority-3 technicians."
                )

        # Rule: future/service-date accept gate
        from .eligibility import is_future_order_visible, is_order_accept_allowed_by_service_date
        if not is_future_order_visible(
            order=locked_order, company_settings=company_settings, now=now,
        ):
            raise ValueError("Future orders are not visible to technicians.")
        if not is_order_accept_allowed_by_service_date(
            order=locked_order, company_settings=company_settings, now=now,
        ):
            raise ValueError("سفارش در تاریخ مقرر و بعد از ساعت مجاز قابل قبول کردن است.")

        # All checks passed — perform the accept
        old_status = locked_order.status
        locked_order.technician = technician
        locked_order.status = Order.Status.WAITING
        locked_order.accepted_at = now
        locked_order.save(update_fields=[
            "technician", "status", "accepted_at", "updated_at",
        ])

        # Create audit log
        OrderStatusLog.objects.create(
            company=locked_order.company,
            order=locked_order,
            old_status=old_status,
            new_status=Order.Status.WAITING,
            changed_by=accepted_by,
            note=f"Accepted by technician: {technician.user.get_full_name()} (P{priority})",
        )

        _emit_order_notification_event("order_accepted_customer", locked_order, accepted_by)

        return locked_order




class OrderEditAssignService:
    """
    Service for handling technician assignment from the admin edit page.

    Differs from OrderAssignService:
    - Called as part of the edit flow (not a standalone action)
    - If technician_id is the same as current, does nothing (no noisy logs)
    - If technician_id is None/cleared, does nothing (preserve current)
    - If technician_id changes, assigns + sets WAITING + accepted_at
    - Only assigns if order is in an assignable status

    This avoids duplicate logs when admin saves the edit form without
    changing the technician.
    """

    ASSIGNABLE_STATUSES = [
        Order.Status.NEW,
        Order.Status.WAITING,
        Order.Status.IN_PROGRESS,
    ]

    @staticmethod
    @transaction.atomic
    def handle_assignment(
        *,
        order: Order,
        technician_id,
        assigned_by: "CompanyUser",
        company,
    ) -> Order:
        """
        Handle technician assignment from admin edit page.

        Args:
            order: The order being edited (already saved).
            technician_id: The technician ID from POST (or None).
            assigned_by: The admin/staff user.
            company: Tenant company.

        Returns:
            The order (possibly updated).
        """
        if not technician_id:
            return order

        # Same technician already assigned → no change needed
        if order.technician_id == technician_id:
            return order

        # Order must be in an assignable status
        if order.status not in OrderEditAssignService.ASSIGNABLE_STATUSES:
            return order

        # Resolve technician
        technician = Technician.objects.filter(
            id=technician_id, company=company, is_available=True,
        ).first()
        if not technician:
            return order

        # Perform assignment
        old_status = order.status
        order.technician = technician
        if not order.accepted_at:
            order.accepted_at = timezone.now()
        if order.status == Order.Status.NEW:
            order.status = Order.Status.WAITING
        order.save(update_fields=["technician", "accepted_at", "status", "updated_at"])

        # Log only if status changed or technician changed
        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=order.status,
            changed_by=assigned_by,
            note=f"Assigned to {technician.user.get_full_name()} from edit page.",
        )

        from .assignment_events import dispatch_order_assigned_events
        dispatch_order_assigned_events(order=order, technician=technician)

        return order



class TechnicianStatusUpdateService:
    """
    Service for technician updating their own order's status.

    Allowed transitions for technician:
    - WAITING → IN_PROGRESS
    - IN_PROGRESS → DONE
    - WAITING/IN_PROGRESS → CANCEL_REQUESTED

    Rules:
    - Technician can only update orders assigned to them
    - Status must be a valid transition
    - DONE sets completed_at
    - Creates OrderStatusLog
    - Does nothing if new_status == current status
    """

    ALLOWED_TRANSITIONS = {
        Order.Status.WAITING: [Order.Status.IN_PROGRESS, Order.Status.CANCEL_REQUESTED],
        Order.Status.IN_PROGRESS: [Order.Status.DONE, Order.Status.CANCEL_REQUESTED],
    }

    @staticmethod
    @transaction.atomic
    def update_status(
        *,
        order: Order,
        technician: "Technician",
        new_status: str,
        updated_by: "CompanyUser",
        note: str = "",
    ) -> Order:
        """
        Technician updates their own order status.

        Args:
            order: The order to update.
            technician: The technician performing the action.
            new_status: The target status.
            updated_by: The user performing the action.
            note: Optional technician note/reason, especially for cancel requests.

        Returns:
            Updated Order instance.

        Raises:
            ValueError: If rules are violated.
        """
        # Rule: order must be assigned to this technician
        if order.technician_id != technician.id:
            raise ValueError("This order is not assigned to you.")

        # Rule: no-op if same status
        if order.status == new_status:
            return order

        # Rule: valid transition
        allowed = TechnicianStatusUpdateService.ALLOWED_TRANSITIONS.get(
            order.status, []
        )
        if new_status not in allowed:
            raise ValueError(
                f"Cannot change status from {order.get_status_display()} "
                f"to {new_status}."
            )

        # Handle CANCEL_REQUESTED with auto-recycle
        if new_status == Order.Status.CANCEL_REQUESTED:
            from apps.tenants.selectors import get_company_settings
            settings = get_company_settings(order.company)
            if settings.auto_recycle_cancel_request:
                # Auto-recycle: cancel old + create replacement
                from .recycle_service import OrderRecycleService
                new_order = OrderRecycleService.recycle(
                    order=order, recycled_by=updated_by,
                )
                return order  # Return the now-cancelled original

        old_status = order.status
        order.status = new_status

        update_fields = ["status", "updated_at"]

        # DONE sets completed_at
        if new_status == Order.Status.DONE:
            order.completed_at = timezone.now()
            if order.final_price == 0:
                order.final_price = order.price_estimate
            update_fields.extend(["completed_at", "final_price"])

        order.save(update_fields=update_fields)

        # Create status log
        status_note = f"Status updated by technician: {technician.user.get_full_name()}"
        if note:
            status_note = f"{status_note}. Note: {note}"

        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=new_status,
            changed_by=updated_by,
            note=status_note,
        )

        # Phase 25: Notify admins when technician requests cancellation
        if new_status == Order.Status.CANCEL_REQUESTED:
            from .cancel_request_events import dispatch_cancel_request_events
            dispatch_cancel_request_events(order=order, reason=note)

        if new_status == Order.Status.IN_PROGRESS:
            _emit_order_notification_event("order_started", order, updated_by)

        if new_status == Order.Status.DONE:
            _emit_order_notification_event("order_completed_customer", order, updated_by)
            _emit_order_notification_event(
                "survey_request_customer", order, updated_by,
                dedup_extra="survey",
            )

        return order

def _emit_order_notification_event(event_key: str, order, actor=None, payload=None, dedup_extra: str = ""):
    # Central order event hook. Order services should not import SMS directly.
    if order is None or not getattr(order, "id", None):
        return None

    try:
        from apps.notifications.services_events import NotificationEventService
        return NotificationEventService.emit(
            event_key=event_key,
            company=getattr(order, "company", None),
            actor=actor,
            target=order,
            payload=payload or {},
            dedup_key=NotificationEventService.build_dedup_key(
                event_key=event_key,
                target=order,
                extra=dedup_extra,
            ),
        )
    except Exception:
        return None

