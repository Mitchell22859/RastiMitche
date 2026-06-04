"""
Orders - Recycle Service.

Handles order cloning/recycling when a cancel-requested order
needs to be replaced with a fresh NEW order.

Used by:
- Auto-recycle (CompanySettings.auto_recycle_cancel_request)
- Admin manual recycle/reopen action
- Admin "بازگشت به چرخه" (return to cycle) action
"""
from typing import Optional

from django.db import transaction
from django.utils import timezone

from apps.accounts.models import CompanyUser

from .eligibility import calculate_priority_visibility_times
from .models import Order, OrderItemValue, OrderStatusLog


class OrderRecycleService:
    """
    Service for recycling/cloning an order into a new replacement.

    Creates a new NEW order copied from the old one, resets assignment fields,
    recalculates priority visibility timestamps, and copies item values.
    """

    @staticmethod
    @transaction.atomic
    def recycle(
        *,
        order: Order,
        recycled_by: Optional[CompanyUser] = None,
        now=None,
    ) -> Order:
        """
        Cancel the old order and create a replacement NEW order.

        Args:
            order: The order to recycle (will be set to CANCELLED).
            recycled_by: The user performing the action (or None for auto).
            now: Current datetime (injectable for testing).

        Returns:
            The new replacement Order.
        """
        if now is None:
            now = timezone.now()

        company = order.company
        priority2_visible_at, priority3_visible_at = calculate_priority_visibility_times(
            company=company,
            base_time=now,
        )

        # Step 1: Cancel the old order
        old_status = order.status
        order.status = Order.Status.CANCELLED
        order.technician = None
        order.save(update_fields=["status", "technician", "updated_at"])

        OrderStatusLog.objects.create(
            company=company,
            order=order,
            old_status=old_status,
            new_status=Order.Status.CANCELLED,
            changed_by=recycled_by,
            note="Order cancelled and recycled into a new order.",
        )

        # Step 2: Create replacement order
        new_order = Order(
            company=company,
            customer=order.customer,
            title=order.title,
            description=order.description,
            address=order.address,
            scheduled_for=order.scheduled_for,
            status=Order.Status.NEW,
            priority=order.priority,
            price_estimate=order.price_estimate,
            final_price=0,
            required_skill=order.required_skill,
            service_category=order.service_category,
            service_subcategory=order.service_subcategory,
            notes=order.notes,
            internal_note=order.internal_note,
            # Reset assignment fields
            technician=None,
            accepted_at=None,
            completed_at=None,
            # Recalculate priority visibility
            priority2_visible_at=priority2_visible_at,
            priority3_visible_at=priority3_visible_at,
        )
        new_order.full_clean()
        new_order.save()

        # Step 3: Create log for new order
        OrderStatusLog.objects.create(
            company=company,
            order=new_order,
            old_status="",
            new_status=Order.Status.NEW,
            changed_by=recycled_by,
            note=f"Replacement order created from cancelled order #{order.id}.",
        )

        # Step 4: Copy OrderItemValues
        OrderRecycleService._copy_item_values(
            source_order=order, target_order=new_order,
        )

        return new_order

    @staticmethod
    def _copy_item_values(*, source_order: Order, target_order: Order):
        """Copy all OrderItemValue rows from source to target order."""
        source_values = OrderItemValue.objects.filter(order=source_order)
        for val in source_values:
            OrderItemValue.objects.create(
                order=target_order,
                item=val.item,
                value_number=val.value_number,
                value_text=val.value_text,
                value_bool=val.value_bool,
            )



class OrderReturnToCycleService:
    """
    Admin action: بازگشت به چرخه (Return to Cycle).

    Business rules:
    - Old order is cancelled (keeps technician for audit history).
    - New order is created with same business info.
    - New order enters dispatch cycle as fresh NEW.
    - Guards against orders with active/paid invoices.
    - Uses NotificationEventService for any events (no direct SMS).
    """

    @staticmethod
    def _has_active_or_paid_invoice(*, order: Order) -> bool:
        """Check if order has a non-cancelled invoice (could cause financial ambiguity)."""
        from apps.invoices.models import Invoice
        return Invoice.objects.filter(
            company=order.company, order=order,
        ).exclude(status=Invoice.Status.CANCELLED).exists()

    @staticmethod
    @transaction.atomic
    def return_to_cycle(
        *,
        order: Order,
        performed_by: Optional[CompanyUser] = None,
        now=None,
    ) -> Order:
        """
        Cancel old order and create a replacement NEW order.

        Differences from OrderRecycleService.recycle():
        - Keeps old order's technician for audit history (does not null it).
        - Guards against active/paid invoices.
        - Copies customer_name, customer_phone, service_date fields.
        - Persian audit log messages.
        - Dispatches order_available_technician event for new order.

        Args:
            order: The order to return to cycle.
            performed_by: Admin performing the action.
            now: Current datetime (injectable for testing).

        Returns:
            The new replacement Order.

        Raises:
            ValueError: If order has active/paid invoices or invalid status.
        """
        if now is None:
            now = timezone.now()

        # Guard: do not cycle orders with active invoices
        if OrderReturnToCycleService._has_active_or_paid_invoice(order=order):
            raise ValueError(
                "این سفارش دارای فاکتور فعال یا پرداخت‌شده است. "
                "برای بازگشت به چرخه ابتدا فاکتور را لغو کنید."
            )

        # Guard: only cancel_requested or in_progress/waiting/new orders can be cycled
        allowed_statuses = [
            Order.Status.CANCEL_REQUESTED,
            Order.Status.NEW,
            Order.Status.WAITING,
            Order.Status.IN_PROGRESS,
        ]
        if order.status not in allowed_statuses:
            raise ValueError("این سفارش در وضعیتی نیست که امکان بازگشت به چرخه داشته باشد.")

        company = order.company
        priority2_visible_at, priority3_visible_at = calculate_priority_visibility_times(
            company=company,
            base_time=now,
        )

        # Step 1: Cancel old order (keep technician for audit)
        old_status = order.status
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])

        # Step 2: Create new replacement order
        new_order = Order(
            company=company,
            customer=order.customer,
            customer_name=order.customer_name,
            customer_phone=order.customer_phone,
            title=order.title,
            description=order.description,
            address=order.address,
            service_date=order.service_date,
            scheduled_for=order.scheduled_for,
            status=Order.Status.NEW,
            priority=order.priority,
            price_estimate=order.price_estimate,
            final_price=0,
            extra_payment=order.extra_payment or 0,
            wage_deduction=order.wage_deduction or 0,
            required_skill=order.required_skill,
            service_category=order.service_category,
            service_subcategory=order.service_subcategory,
            notes=order.notes,
            internal_note=order.internal_note,
            # Reset assignment fields
            technician=None,
            accepted_at=None,
            completed_at=None,
            # Fresh dispatch cycle
            priority2_visible_at=priority2_visible_at,
            priority3_visible_at=priority3_visible_at,
        )
        new_order.full_clean()
        new_order.save()

        # Step 3: Audit logs
        OrderStatusLog.objects.create(
            company=company,
            order=order,
            old_status=old_status,
            new_status=Order.Status.CANCELLED,
            changed_by=performed_by,
            note=f"بازگشت به چرخه: این سفارش لغو شد و سفارش جدید #{new_order.id} از روی آن ساخته شد.",
        )

        OrderStatusLog.objects.create(
            company=company,
            order=new_order,
            old_status="",
            new_status=Order.Status.NEW,
            changed_by=performed_by,
            note=f"این سفارش از بازگشت به چرخه سفارش #{order.id} ساخته شد.",
        )

        # Step 4: Copy OrderItemValues
        OrderRecycleService._copy_item_values(
            source_order=order, target_order=new_order,
        )

        # Step 5: Dispatch order_available_technician event for new order
        from .order_events import dispatch_order_available_events
        dispatch_order_available_events(order=new_order)

        return new_order
