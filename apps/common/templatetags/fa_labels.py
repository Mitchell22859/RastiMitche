from __future__ import annotations

import datetime
from django import template
from django.utils import timezone

register = template.Library()

STATUS_LABELS = {
    "new": "\u062c\u062f\u06cc\u062f",
    "pending": "\u062f\u0631 \u0627\u0646\u062a\u0638\u0627\u0631",
    "waiting": "\u062f\u0631 \u0627\u0646\u062a\u0638\u0627\u0631",
    "open": "\u0628\u0627\u0632",
    "closed": "\u0628\u0633\u062a\u0647 \u0634\u062f\u0647",
    "active": "\u0641\u0639\u0627\u0644",
    "inactive": "\u063a\u06cc\u0631\u0641\u0639\u0627\u0644",
    "enabled": "\u0641\u0639\u0627\u0644",
    "disabled": "\u063a\u06cc\u0631\u0641\u0639\u0627\u0644",
    "approved": "\u062a\u0623\u06cc\u06cc\u062f \u0634\u062f\u0647",
    "rejected": "\u0631\u062f \u0634\u062f\u0647",
    "true": "\u0628\u0644\u0647",
    "false": "\u062e\u06cc\u0631",
    "assigned": "\u062a\u062e\u0635\u06cc\u0635 \u062f\u0627\u062f\u0647 \u0634\u062f\u0647",
    "accepted": "\u067e\u0630\u06cc\u0631\u0641\u062a\u0647 \u0634\u062f\u0647",
    "in_progress": "\u062f\u0631 \u062d\u0627\u0644 \u0627\u0646\u062c\u0627\u0645",
    "started": "\u0634\u0631\u0648\u0639 \u0634\u062f\u0647",
    "completed": "\u062a\u06a9\u0645\u06cc\u0644 \u0634\u062f\u0647",
    "done": "\u0627\u0646\u062c\u0627\u0645 \u0634\u062f\u0647",
    "cancel_requested": "\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0644\u063a\u0648",
    "cancel_approved": "\u0644\u063a\u0648 \u062a\u0623\u06cc\u06cc\u062f \u0634\u062f\u0647",
    "cancel_rejected": "\u0644\u063a\u0648 \u0631\u062f \u0634\u062f\u0647",
    "cancelled": "\u0644\u063a\u0648 \u0634\u062f\u0647",
    "canceled": "\u0644\u063a\u0648 \u0634\u062f\u0647",
    "rescheduled": "\u0632\u0645\u0627\u0646\u200c\u0628\u0646\u062f\u06cc \u0645\u062c\u062f\u062f",
    "draft": "\u067e\u06cc\u0634\u200c\u0646\u0648\u06cc\u0633",
    "issued": "\u0635\u0627\u062f\u0631 \u0634\u062f\u0647",
    "paid": "\u067e\u0631\u062f\u0627\u062e\u062a \u0634\u062f\u0647",
    "unpaid": "\u067e\u0631\u062f\u0627\u062e\u062a \u0646\u0634\u062f\u0647",
    "partially_paid": "\u067e\u0631\u062f\u0627\u062e\u062a \u0646\u0627\u0642\u0635",
    "overdue": "\u0633\u0631\u0631\u0633\u06cc\u062f \u06af\u0630\u0634\u062a\u0647",
    "refunded": "\u0628\u0631\u06af\u0634\u062a \u062e\u0648\u0631\u062f\u0647",
    "void": "\u0628\u0627\u0637\u0644 \u0634\u062f\u0647",
    "success": "\u0645\u0648\u0641\u0642",
    "successful": "\u0645\u0648\u0641\u0642",
    "failed": "\u0646\u0627\u0645\u0648\u0641\u0642",
    "started_payment": "\u067e\u0631\u062f\u0627\u062e\u062a \u0634\u0631\u0648\u0639 \u0634\u062f\u0647",
    "queued": "\u062f\u0631 \u0635\u0641 \u0627\u0631\u0633\u0627\u0644",
    "sending": "\u062f\u0631 \u062d\u0627\u0644 \u0627\u0631\u0633\u0627\u0644",
    "sent": "\u0627\u0631\u0633\u0627\u0644 \u0634\u062f\u0647",
    "delivered": "\u062a\u062d\u0648\u06cc\u0644 \u0634\u062f\u0647",
    "recorded": "\u062b\u0628\u062a \u0634\u062f\u0647",
    "dispatched": "\u067e\u0631\u062f\u0627\u0632\u0634 \u0634\u062f\u0647",
    "processed": "\u067e\u0631\u062f\u0627\u0632\u0634 \u0634\u062f\u0647",
    "skipped": "\u0631\u062f \u0634\u062f\u0647",
    "trial": "\u0622\u0632\u0645\u0627\u06cc\u0634\u06cc",
    "expired": "\u0645\u0646\u0642\u0636\u06cc \u0634\u062f\u0647"
}

STATUS_CSS_GROUPS = {
    "success": [
        "done",
        "completed",
        "paid",
        "success",
        "successful",
        "sent",
        "delivered",
        "active",
        "accepted",
        "approved",
        "dispatched",
        "processed"
    ],
    "danger": [
        "cancelled",
        "canceled",
        "failed",
        "rejected",
        "inactive",
        "disabled",
        "void",
        "cancel_rejected",
        "expired"
    ],
    "warning": [
        "pending",
        "waiting",
        "draft",
        "issued",
        "unpaid",
        "overdue",
        "cancel_requested",
        "queued",
        "sending",
        "started_payment",
        "trial"
    ],
    "info": [
        "new",
        "assigned",
        "in_progress",
        "started",
        "rescheduled",
        "recorded",
        "open",
        "enabled",
        "partially_paid"
    ],
    "neutral": [
        "closed",
        "skipped",
        "refunded"
    ]
}


def _normalize_status_key(value):
    if value is None:
        return ""
    key = str(value).strip()
    if not key:
        return ""
    return key.replace("-", "_").replace(" ", "_").lower()


def _to_local_datetime(value):
    if isinstance(value, datetime.datetime):
        try:
            if timezone.is_aware(value):
                return timezone.localtime(value)
        except Exception:
            pass
    return value


def _to_jalali(value):
    if not value:
        return None

    value = _to_local_datetime(value)

    try:
        import jdatetime
        if isinstance(value, datetime.datetime):
            return jdatetime.datetime.fromgregorian(datetime=value)
        if isinstance(value, datetime.date):
            return jdatetime.date.fromgregorian(date=value)
    except Exception:
        pass

    try:
        from persiantools.jdatetime import JalaliDate, JalaliDateTime
        if isinstance(value, datetime.datetime):
            return JalaliDateTime.to_jalali(value)
        if isinstance(value, datetime.date):
            return JalaliDate.to_jalali(value)
    except Exception:
        pass

    return value


@register.filter(name="jalali_date")
def jalali_date(value):
    j = _to_jalali(value)
    if not j:
        return "-"
    try:
        return f"{j.year:04d}/{j.month:02d}/{j.day:02d}"
    except Exception:
        try:
            return _to_local_datetime(value).strftime("%Y/%m/%d")
        except Exception:
            return str(value)


@register.filter(name="jalali_datetime")
def jalali_datetime(value):
    j = _to_jalali(value)
    if not j:
        return "-"
    try:
        hour = getattr(j, "hour", 0)
        minute = getattr(j, "minute", 0)
        return f"{j.year:04d}/{j.month:02d}/{j.day:02d} {hour:02d}:{minute:02d}"
    except Exception:
        try:
            return _to_local_datetime(value).strftime("%Y/%m/%d %H:%M")
        except Exception:
            return str(value)


@register.filter(name="status_fa")
def status_fa(value):
    key = _normalize_status_key(value)
    if not key:
        return "-"
    return STATUS_LABELS.get(key, str(value))


@register.filter(name="fa_status")
def fa_status(value):
    return status_fa(value)


@register.filter(name="sms_status_fa")
def sms_status_fa(value):
    return status_fa(value)


@register.filter(name="order_status_fa")
def order_status_fa(value):
    return status_fa(value)


@register.filter(name="invoice_status_fa")
def invoice_status_fa(value):
    return status_fa(value)


@register.filter(name="payment_status_fa")
def payment_status_fa(value):
    return status_fa(value)


@register.filter(name="status_css")
def status_css(value):
    key = _normalize_status_key(value)
    for group, keys in STATUS_CSS_GROUPS.items():
        if key in keys:
            return group
    return "neutral"


@register.filter(name="status_badge_classes")
def status_badge_classes(value):
    group = status_css(value)
    classes = {
        "success": "status-badge status-success",
        "danger": "status-badge status-danger",
        "warning": "status-badge status-warning",
        "info": "status-badge status-info",
        "neutral": "status-badge status-neutral",
    }
    return classes.get(group, classes["neutral"])


@register.filter(name="fa_bool")
def fa_bool(value):
    return "بله" if bool(value) else "خیر"


@register.filter(name="rial")
def rial(value):
    try:
        return f"{int(value):,} ریال"
    except Exception:
        return str(value)


@register.filter(name="toman")
def toman(value):
    try:
        return f"{int(value):,} تومان"
    except Exception:
        return str(value)
