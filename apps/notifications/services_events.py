"""Central event entrypoint.

Use this service from orders/invoices/payments/etc.
Do not import SMS services from business apps.
"""
from __future__ import annotations

from django.db import transaction

from .models import NotificationEvent


class NotificationEventService:
    @staticmethod
    def _target_metadata(target) -> dict:
        if target is None:
            return {"target_app": "", "target_model": "", "target_id": None}

        meta = getattr(target, "_meta", None)
        return {
            "target_app": getattr(meta, "app_label", "") if meta else "",
            "target_model": getattr(meta, "object_name", target.__class__.__name__) if meta else target.__class__.__name__,
            "target_id": getattr(target, "id", None),
        }

    @staticmethod
    def build_dedup_key(*, event_key: str, target=None, extra: str = "") -> str:
        data = NotificationEventService._target_metadata(target)
        parts = [str(event_key or "")]
        if data["target_app"] and data["target_model"] and data["target_id"]:
            parts += [data["target_app"], data["target_model"], str(data["target_id"])]
        if extra:
            parts.append(str(extra))
        return ":".join(parts)

    @staticmethod
    def emit(
        *,
        event_key: str,
        company=None,
        actor=None,
        target=None,
        payload: dict | None = None,
        dedup_key: str | None = None,
        dispatch: bool = True,
        use_on_commit: bool = True,
    ) -> NotificationEvent:
        if company is None and target is not None:
            company = getattr(target, "company", None)

        target_data = NotificationEventService._target_metadata(target)
        payload = payload or {}
        dedup_key = dedup_key or NotificationEventService.build_dedup_key(event_key=event_key, target=target)

        if dedup_key:
            existing = NotificationEvent.objects.filter(dedup_key=dedup_key).order_by("-id").first()
            if existing is not None:
                return existing

        event = NotificationEvent.objects.create(
            company=company,
            event_key=event_key,
            actor=actor,
            payload_json=payload,
            dedup_key=dedup_key or "",
            **target_data,
        )

        if dispatch:
            def _dispatch():
                from .dispatchers import NotificationDispatcher
                NotificationDispatcher.dispatch(event)

            if use_on_commit:
                transaction.on_commit(_dispatch)
            else:
                _dispatch()

        return event
