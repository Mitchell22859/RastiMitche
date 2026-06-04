"""Central notification dispatcher."""
from __future__ import annotations

from django.utils import timezone

from .event_catalog import Payer, Recipient, get_event_definition
from .message_builders import build_context_for_event, fallback_message_for_event
from .recipients import (
    get_available_technician_recipients,
    get_company_admin_recipients,
    get_direct_user_recipient,
    get_invoice_customer_recipient,
    get_order_customer_recipient,
    get_order_technician_recipient,
    get_platform_owner_recipients,
    get_technician_profile_recipient,
)


class NotificationDispatcher:
    @staticmethod
    def _target_for_event(event):
        if not event.target_app or not event.target_model or not event.target_id:
            return None

        try:
            from django.apps import apps
            model = apps.get_model(event.target_app, event.target_model)
            return model.objects.filter(id=event.target_id).first()
        except Exception:
            return None

    @staticmethod
    def _recipients_for_event(*, definition, company, target) -> list[dict]:
        if definition.recipient == Recipient.COMPANY_ADMIN:
            return get_company_admin_recipients(company)

        if definition.recipient == Recipient.PLATFORM_OWNER:
            return get_platform_owner_recipients()

        if definition.recipient == Recipient.OPERATOR:
            return get_direct_user_recipient(target) if target is not None else []

        if definition.recipient == Recipient.CUSTOMER:
            if target is None:
                return []
            model_name = target.__class__.__name__.lower()
            if model_name == "invoice":
                return get_invoice_customer_recipient(target)
            if model_name == "order":
                return get_order_customer_recipient(target)
            return []

        if definition.recipient == Recipient.TECHNICIAN:
            if target is None:
                return []
            model_name = target.__class__.__name__.lower()
            if model_name == "order":
                return get_order_technician_recipient(target)
            if model_name == "technician":
                return get_technician_profile_recipient(target)
            return get_direct_user_recipient(target)

        if definition.recipient == Recipient.AVAILABLE_TECHNICIANS:
            return get_available_technician_recipients(target) if target is not None else []

        return []

    @staticmethod
    def dispatch(event):
        definition = get_event_definition(event.event_key)
        if definition is None:
            event.status = event.Status.SKIPPED
            event.result_message = f"Unknown event key: {event.event_key}"
            event.dispatched_at = timezone.now()
            event.save(update_fields=["status", "result_message", "dispatched_at", "updated_at"])
            return event

        company = event.company
        target = NotificationDispatcher._target_for_event(event)
        context = build_context_for_event(event.event_key, target, event.payload_json)
        recipients = NotificationDispatcher._recipients_for_event(definition=definition, company=company, target=target)

        if not recipients:
            event.status = event.Status.SKIPPED
            event.result_message = "No recipient found."
            event.dispatched_at = timezone.now()
            event.save(update_fields=["status", "result_message", "dispatched_at", "updated_at"])
            return event

        fallback = fallback_message_for_event(event.event_key, context)
        queued_count = 0

        if definition.payer == Payer.COMPANY:
            from apps.sms.services import SMSQueueFromTemplateService
            for recipient in recipients:
                sms = SMSQueueFromTemplateService.queue_from_template(
                    company=company,
                    template_key=event.event_key,
                    phone_number=recipient["phone"],
                    context=context,
                    fallback_message=fallback,
                    order_id=event.target_id if event.target_model == "Order" else None,
                    invoice_id=event.target_id if event.target_model == "Invoice" else None,
                )
                if sms is not None:
                    queued_count += 1

        elif definition.payer == Payer.PLATFORM:
            from apps.platform_core.services_platform_sms import PlatformSMSQueueService
            for recipient in recipients:
                sms = PlatformSMSQueueService.queue(
                    recipient_company=company,
                    template_key=event.event_key,
                    phone_number=recipient["phone"],
                    message=fallback,
                )
                if sms is not None:
                    queued_count += 1

        event.status = event.Status.DISPATCHED
        event.result_message = f"Queued messages: {queued_count}"
        event.dispatched_at = timezone.now()
        event.save(update_fields=["status", "result_message", "dispatched_at", "updated_at"])
        return event
