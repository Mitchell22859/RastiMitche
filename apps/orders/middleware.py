"""Order notification auto-dispatch middleware.

This is a lightweight lazy scheduler for projects that do not yet run Celery or
cron. It automatically dispatches due technician notifications when tenant users
load relevant pages, with a short per-company throttle to avoid doing the same
scan on every request.
"""
from __future__ import annotations

import logging

from django.core.cache import cache

from apps.accounts.models import UserRole

logger = logging.getLogger(__name__)


class OrderNotificationDispatchMiddleware:
    """Dispatch due technician notifications automatically during normal usage.

    This is not a replacement for a production-grade background worker, but it
    removes the need to run the management command manually during normal admin
    and technician usage.
    """

    THROTTLE_SECONDS = 45
    RELEVANT_PATH_PARTS = ("/orders/", "/notifications/", "/tech/", "/admin/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        self._maybe_dispatch(request)
        return response

    def _maybe_dispatch(self, request) -> None:
        try:
            if request.method != "GET":
                return
            company = getattr(request, "company", None)
            user = getattr(request, "user", None)
            if company is None or not getattr(user, "is_authenticated", False):
                return
            if getattr(user, "role", None) not in {
                UserRole.COMPANY_ADMIN,
                UserRole.COMPANY_STAFF,
                UserRole.TECHNICIAN,
            }:
                return
            path = getattr(request, "path", "") or ""
            if not any(part in path for part in self.RELEVANT_PATH_PARTS):
                return

            cache_key = f"order-notification-auto-dispatch:{company.id}"
            if not cache.add(cache_key, "1", timeout=self.THROTTLE_SECONDS):
                return

            from apps.orders.technician_notifications import (
                dispatch_due_order_notifications_for_company,
            )

            dispatch_due_order_notifications_for_company(company=company)
        except Exception:
            logger.exception("Automatic order notification dispatch failed.")
