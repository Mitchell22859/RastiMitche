"""
Notifications - Service Layer.

Handles notification creation and management.
Also provides event hooks for other services to trigger notifications.

Phase 30:
- NotificationSettingService controls whether each business event may create
  in-app notifications and/or SMS.
- Event hooks pass explicit event keys so admins can enable/disable them from
  /<company_code>/admin/settings/notifications/.
"""
from __future__ import annotations

from typing import Optional

from apps.notifications.sync import sync_sms_template_from_notification_setting

from django.utils import timezone

from apps.accounts.models import CompanyUser, UserRole

from .models import Notification, NotificationSetting


class NotificationSettingService:
    """Read/write helpers for per-company notification switches."""

    @staticmethod
    def default_rows() -> list[dict]:
        """Return default notification/SMS settings for every event in the catalog.

        This keeps NotificationSetting synchronized with the central event matrix:
        - all 46 events get an in-app setting row
        - SMS-enabled defaults follow EventDefinition.default_sms_enabled
        - internal-only events always get sms_enabled=False
        """
        from apps.notifications.event_catalog import EVENT_DEFINITIONS

        rows: list[dict] = []
        for definition in EVENT_DEFINITIONS.values():
            rows.append({
                "event_key": definition.key,
                "title": definition.title,
                "in_app_enabled": bool(definition.default_in_app_enabled),
                "sms_enabled": bool(definition.sms_supported and definition.default_sms_enabled),
            })
        return rows



    @classmethod
    def ensure_defaults(cls, *, company) -> list[NotificationSetting]:
        rows: list[NotificationSetting] = []
        for item in cls.default_rows():
            row, _ = NotificationSetting.objects.get_or_create(
                company=company,
                event_key=item["event_key"],
                defaults={
                    "title": item["title"],
                    "in_app_enabled": item["in_app_enabled"],
                    "sms_enabled": item["sms_enabled"],
                },
            )
            if not row.title:
                row.title = item["title"]
                row.save(update_fields=["title", "updated_at"])
            rows.append(row)
        return rows

    @staticmethod
    def is_in_app_enabled(*, company, event_key: str = "") -> bool:
        if not event_key:
            return True
        setting = NotificationSetting.objects.filter(
            company=company,
            event_key=str(event_key),
        ).first()
        if setting is None:
            return True
        return setting.in_app_enabled

    @staticmethod
    def is_sms_enabled(*, company, event_key: str = "") -> bool:
        if not event_key:
            return True
        setting = NotificationSetting.objects.filter(
            company=company,
            event_key=str(event_key),
        ).first()
        if setting is None:
            return True
        return setting.sms_enabled

    @staticmethod
    def update_from_post(*, company, post_data) -> list[NotificationSetting]:
        rows = NotificationSettingService.ensure_defaults(company=company)
        by_key = {row.event_key: row for row in rows}

        for item in NotificationSettingService.default_rows():
            key = str(item["event_key"])
            row = by_key.get(key)
            if row is None:
                continue
            row.in_app_enabled = bool(post_data.get(f"in_app_{key}"))
            row.sms_enabled = bool(post_data.get(f"sms_{key}"))
            row.save(update_fields=["in_app_enabled", "sms_enabled", "updated_at"])

            try:
                from apps.sms.models import SMSTemplate
                SMSTemplate.objects.filter(company=company, key=key).update(
                    is_active=row.sms_enabled,
                )
            except Exception:
                pass

        return NotificationSettingService.ensure_defaults(company=company)


class NotificationCreateService:
    """Service for creating notifications."""

    @staticmethod
    def create(
        *,
        company,
        recipient: CompanyUser,
        notification_type: str,
        title: str,
        message: str,
        related_order=None,
        related_invoice=None,
        event_key: str = "",
    ) -> Optional[Notification]:
        """Create a notification for a user if the event is enabled."""
        if not NotificationSettingService.is_in_app_enabled(company=company, event_key=event_key):
            return None

        return Notification.objects.create(
            company=company,
            recipient=recipient,
            notification_type=notification_type,
            title=title,
            message=message,
            related_order=related_order,
            related_invoice=related_invoice,
        )

    @staticmethod
    def create_once(
        *,
        company,
        recipient: CompanyUser,
        notification_type: str,
        title: str,
        message: str,
        related_order=None,
        related_invoice=None,
        event_key: str = "",
    ) -> tuple[Optional[Notification], bool]:
        """Create a notification once per recipient/type/related object."""
        if not NotificationSettingService.is_in_app_enabled(company=company, event_key=event_key):
            return None, False

        lookup = {
            "company": company,
            "recipient": recipient,
            "notification_type": notification_type,
            "related_order": related_order,
            "related_invoice": related_invoice,
        }
        notification, created = Notification.objects.get_or_create(
            **lookup,
            defaults={
                "title": title,
                "message": message,
            },
        )
        return notification, created

    @staticmethod
    def notify_company_admins(
        *,
        company,
        notification_type: str,
        title: str,
        message: str,
        related_order=None,
        related_invoice=None,
        event_key: str = "",
    ) -> list[Notification]:
        """Send notification to all admins/staff of a company."""
        admins = CompanyUser.objects.filter(
            company=company,
            role__in=[UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF],
            is_active=True,
        )
        notifications = []
        for admin in admins:
            notification = NotificationCreateService.create(
                company=company,
                recipient=admin,
                notification_type=notification_type,
                title=title,
                message=message,
                related_order=related_order,
                related_invoice=related_invoice,
                event_key=event_key,
            )
            if notification is not None:
                notifications.append(notification)
        return notifications


class NotificationMarkReadService:
    """Service for marking notifications as read."""

    @staticmethod
    def mark_read(*, notification: Notification) -> Notification:
        """Mark a single notification as read."""
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=["is_read", "read_at", "updated_at"])
        return notification

    @staticmethod
    def mark_all_read(*, company, user: CompanyUser) -> int:
        """Mark all unread notifications as read for a user. Returns count."""
        count = Notification.objects.filter(
            company=company, recipient=user, is_read=False
        ).update(is_read=True, read_at=timezone.now())
        return count


# =============================================================================
# EVENT HOOKS
# =============================================================================


class NotificationEventHooks:
    """
    Event hooks for triggering notifications from services.

    These are called AFTER primary operations succeed.
    """

    @staticmethod
    def on_order_created(*, order) -> None:
        """Notify company admin/staff of new public/admin order."""
        NotificationCreateService.notify_company_admins(
            company=order.company,
            notification_type=Notification.NotificationType.ORDER_CREATED,
            title="ط³ظپط§ط±ط´ ط¬ط¯غŒط¯ ط«ط¨طھ ط´ط¯",
            message=f"ط³ظپط§ط±ط´ ط¬ط¯غŒط¯ #{order.id}: {order.title}",
            related_order=order,
            event_key=NotificationSetting.EventKey.ORDER_CREATED_ADMIN,
        )

    @staticmethod
    def on_order_accepted(*, order) -> None:
        """Notify customer that their order was accepted/assigned."""
        if order.customer and order.customer.user:
            NotificationCreateService.create(
                company=order.company,
                recipient=order.customer.user,
                notification_type=Notification.NotificationType.ORDER_ACCEPTED,
                title="ط³ظپط§ط±ط´ طھط§غŒغŒط¯ ط´ط¯",
                message=f"ط³ظپط§ط±ط´ #{order.id} ط´ظ…ط§ طھظˆط³ط· طھع©ظ†ط³غŒظ† ظ¾ط°غŒط±ظپطھظ‡ ط´ط¯.",
                related_order=order,
                event_key=NotificationSetting.EventKey.ORDER_ACCEPTED_CUSTOMER,
            )

    @staticmethod
    def on_order_completed(*, order) -> None:
        """Notify customer that their order is complete."""
        if order.customer and order.customer.user:
            NotificationCreateService.create(
                company=order.company,
                recipient=order.customer.user,
                notification_type=Notification.NotificationType.ORDER_COMPLETED,
                title="ط³ظپط§ط±ط´ طھع©ظ…غŒظ„ ط´ط¯",
                message=f"ط³ظپط§ط±ط´ #{order.id} ط´ظ…ط§ طھع©ظ…غŒظ„ ط´ط¯.",
                related_order=order,
                event_key=NotificationSetting.EventKey.ORDER_COMPLETED_CUSTOMER,
            )

    @staticmethod
    def on_invoice_issued(*, invoice) -> None:
        """Notify customer that invoice is ready for payment."""
        if invoice.customer and invoice.customer.user:
            NotificationCreateService.create(
                company=invoice.company,
                recipient=invoice.customer.user,
                notification_type=Notification.NotificationType.INVOICE_ISSUED,
                title="ظپط§ع©طھظˆط± طµط§ط¯ط± ط´ط¯",
                message=f"ظپط§ع©طھظˆط± {invoice.invoice_number} ط¢ظ…ط§ط¯ظ‡ ظ¾ط±ط¯ط§ط®طھ ط§ط³طھ.",
                related_invoice=invoice,
                event_key=NotificationSetting.EventKey.INVOICE_ISSUED_CUSTOMER,
            )

    @staticmethod
    def on_payment_paid(*, payment) -> None:
        """Notify customer + admins that payment succeeded."""
        invoice = payment.invoice
        if invoice and invoice.customer and invoice.customer.user:
            NotificationCreateService.create(
                company=payment.company,
                recipient=invoice.customer.user,
                notification_type=Notification.NotificationType.PAYMENT_PAID,
                title="ظ¾ط±ط¯ط§ط®طھ ظ…ظˆظپظ‚",
                message=f"ظ¾ط±ط¯ط§ط®طھ ظپط§ع©طھظˆط± {invoice.invoice_number} ط¨ط§ ظ…ظˆظپظ‚غŒطھ ط§ظ†ط¬ط§ظ… ط´ط¯.",
                related_invoice=invoice,
                event_key=NotificationSetting.EventKey.PAYMENT_SUCCESS_CUSTOMER,
            )

        NotificationCreateService.notify_company_admins(
            company=payment.company,
            notification_type=Notification.NotificationType.PAYMENT_PAID,
            title="ظ¾ط±ط¯ط§ط®طھ ط¯ط±غŒط§ظپطھ ط´ط¯",
            message=f"ظ¾ط±ط¯ط§ط®طھ ط¨ظ‡ ظ…ط¨ظ„ط؛ {payment.amount} ط¯ط±غŒط§ظپطھ ط´ط¯.",
            related_invoice=invoice,
            event_key=NotificationSetting.EventKey.PAYMENT_SUCCESS_CUSTOMER,
        )

    @staticmethod
    def on_payment_failed(*, payment) -> None:
        """Notify customer that payment failed."""
        invoice = payment.invoice
        if invoice and invoice.customer and invoice.customer.user:
            NotificationCreateService.create(
                company=payment.company,
                recipient=invoice.customer.user,
                notification_type=Notification.NotificationType.PAYMENT_FAILED,
                title="ظ¾ط±ط¯ط§ط®طھ ظ†ط§ظ…ظˆظپظ‚",
                message=f"ظ¾ط±ط¯ط§ط®طھ ظپط§ع©طھظˆط± {invoice.invoice_number} ظ†ط§ظ…ظˆظپظ‚ ط¨ظˆط¯.",
                related_invoice=invoice,
                event_key=NotificationSetting.EventKey.PAYMENT_FAILED_CUSTOMER,
            )
