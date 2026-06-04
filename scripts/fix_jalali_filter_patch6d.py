import re
from pathlib import Path

root = Path.cwd()

tag_dir = root / "apps" / "common" / "templatetags"
tag_dir.mkdir(parents=True, exist_ok=True)

(tag_dir / "__init__.py").write_text("", encoding="utf-8")

(tag_dir / "fa_labels.py").write_text(r'''
from __future__ import annotations

import datetime
from django import template
from django.utils import timezone

register = template.Library()


def _to_jalali(value):
    if not value:
        return None

    if isinstance(value, datetime.datetime):
        try:
            value = timezone.localtime(value)
        except Exception:
            pass

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
            return value.strftime("%Y/%m/%d")
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
            return value.strftime("%Y/%m/%d %H:%M")
        except Exception:
            return str(value)


@register.filter(name="fa_status")
def fa_status(value):
    if value is None:
        return "-"
    key = str(value).strip()
    labels = {
        "queued": "در صف ارسال",
        "sending": "در حال ارسال",
        "sent": "ارسال شده",
        "delivered": "تحویل شده",
        "failed": "ارسال ناموفق",
        "cancelled": "لغو شده",
        "canceled": "لغو شده",

        "new": "جدید",
        "pending": "در انتظار",
        "accepted": "پذیرفته شده",
        "assigned": "تخصیص داده شده",
        "in_progress": "در حال انجام",
        "started": "شروع شده",
        "completed": "تکمیل شده",
        "done": "انجام شده",
        "cancel_requested": "درخواست لغو",
        "cancelled": "لغو شده",
        "rejected": "رد شده",
        "paid": "پرداخت شده",
        "unpaid": "پرداخت نشده",
        "draft": "پیشنویس",
        "issued": "صادر شده",
    }
    return labels.get(key, key)
''', encoding="utf-8")


templates = [
    root / "templates" / "notifications" / "list.html",
    root / "templates" / "notifications" / "_notification_list_inner.html",
    root / "templates" / "reports" / "list.html",
    root / "templates" / "sms" / "outbox_admin_list.html",
    root / "templates" / "sms" / "outbox_detail.html",
]

load_line = "{% load fa_labels %}"

for path in templates:
    if not path.exists():
        continue

    text = path.read_text(encoding="utf-8-sig")
    if load_line in text:
        continue

    m = re.match(r"(\s*\{\%\s*extends\s+[^%]+%\}\s*\r?\n)", text)
    if m:
        text = text[:m.end()] + load_line + "\n" + text[m.end():]
    else:
        text = load_line + "\n" + text

    path.write_text(text, encoding="utf-8")

print("Fixed jalali_datetime/fa_status filters and loaded fa_labels in target templates.")
