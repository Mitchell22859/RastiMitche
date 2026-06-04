"""
Phase 25: Cancel Request Review Service.

Admin/operator actions to approve or reject a technician's cancel request.

Business rules:
- Only orders in CANCEL_REQUESTED status can be reviewed.
- Only COMPANY_ADMIN or COMPANY_STAFF of the same company can review.
- Approve: sets status to CANCELLED, logs, notifies technician.
- Reject: restores the previous active status (from OrderStatusLog), logs, notifies technician.
"""
from django.db import transaction

from apps.accounts.models import CompanyUser

from .cancel_request_events import dispatch_cancel_approved_events, dispatch_cancel_rejected_events
from .models import Order, OrderStatusLog


class OrderCancelReviewService:
    """Service for admin review of technician cancel requests."""

    @staticmethod
    @transaction.atomic
    def approve(
        *,
        order: Order,
        approved_by: CompanyUser,
        note: str = "",
    ) -> Order:
        """
        Approve a cancel request — set order to CANCELLED.

        Args:
            order: Must be in CANCEL_REQUESTED status.
            approved_by: Admin/staff user.
            note: Optional admin note.

        Returns:
            Updated order.

        Raises:
            ValueError: If order is not in CANCEL_REQUESTED status or company mismatch.
        """
        if order.company_id != approved_by.company_id:
            raise ValueError("Access denied.")

        if order.status != Order.Status.CANCEL_REQUESTED:
            raise ValueError("سفارش در وضعیت درخواست لغو نیست.")

        old_status = order.status
        order.status = Order.Status.CANCELLED
        order.save(update_fields=["status", "updated_at"])

        log_note = "درخواست لغو توسط مدیر تایید شد."
        if note:
            log_note = f"{log_note} یادداشت: {note}"

        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=Order.Status.CANCELLED,
            changed_by=approved_by,
            note=log_note,
        )

        dispatch_cancel_approved_events(order=order)
        return order

    @staticmethod
    @transaction.atomic
    def reject(
        *,
        order: Order,
        rejected_by: CompanyUser,
        note: str = "",
    ) -> Order:
        """
        Reject a cancel request — restore the order to its previous active status.

        Restoration logic:
        1. Look at the latest OrderStatusLog where to_status == CANCEL_REQUESTED
           and use its from_status.
        2. Fallback: if technician is assigned → WAITING, else → NEW.

        Args:
            order: Must be in CANCEL_REQUESTED status.
            rejected_by: Admin/staff user.
            note: Optional admin note.

        Returns:
            Updated order.

        Raises:
            ValueError: If order is not in CANCEL_REQUESTED status or company mismatch.
        """
        if order.company_id != rejected_by.company_id:
            raise ValueError("Access denied.")

        if order.status != Order.Status.CANCEL_REQUESTED:
            raise ValueError("سفارش در وضعیت درخواست لغو نیست.")

        # Determine previous status from log
        restored_status = OrderCancelReviewService._determine_restore_status(order)

        old_status = order.status
        order.status = restored_status
        order.save(update_fields=["status", "updated_at"])

        log_note = f"درخواست لغو توسط مدیر رد شد. وضعیت به {order.get_status_display()} بازگشت."
        if note:
            log_note = f"{log_note} یادداشت: {note}"

        OrderStatusLog.objects.create(
            company=order.company,
            order=order,
            old_status=old_status,
            new_status=restored_status,
            changed_by=rejected_by,
            note=log_note,
        )

        dispatch_cancel_rejected_events(order=order)
        return order

    @staticmethod
    def _determine_restore_status(order: Order) -> str:
        """
        Determine which status to restore when rejecting a cancel request.

        Reads the most recent log entry that transitioned INTO CANCEL_REQUESTED
        and uses its from_status. Falls back to WAITING/NEW based on assignment.
        """
        log_entry = (
            OrderStatusLog.objects.filter(
                order=order,
                company=order.company,
                new_status=Order.Status.CANCEL_REQUESTED,
            )
            .order_by("-created_at")
            .first()
        )

        if log_entry and log_entry.old_status:
            candidate = log_entry.old_status
            # Only restore to a sensible active status
            active_statuses = [
                Order.Status.NEW,
                Order.Status.WAITING,
                Order.Status.IN_PROGRESS,
            ]
            if candidate in active_statuses:
                return candidate

        # Fallback
        if order.technician_id:
            return Order.Status.WAITING
        return Order.Status.NEW
