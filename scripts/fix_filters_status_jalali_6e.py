import re
from pathlib import Path

root = Path.cwd()
backup_dir = root / "patch_backups" / "fix_template_filters_status_jalali_6e"
backup_dir.mkdir(parents=True, exist_ok=True)

# Use apps/common because previous patch already used {% load fa_labels %}
tag_dir = root / "apps" / "common" / "templatetags"
tag_dir.mkdir(parents=True, exist_ok=True)
(tag_dir / "__init__.py").write_text("", encoding="utf-8")

fa_labels_path = tag_dir / "fa_labels.py"

if fa_labels_path.exists():
    (backup_dir / "fa_labels.py.bak").write_text(fa_labels_path.read_text(encoding="utf-8-sig"), encoding="utf-8")

fa_labels_path.write_text(r'''
from __future__ import annotations

import datetime
from django import template
from django.utils import timezone

register = template.Library()


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


_STATUS_LABELS = {
    # SMS outbox
    "queued": "در صف ارسال",
    "sending": "در حال ارسال",
    "sent": "ارسال شده",
    "delivered": "تحویل شده",
    "failed": "ارسال ناموفق",
    "cancelled": "لغو شده",
    "canceled": "لغو شده",

    # Notification/event
    "recorded": "ثبت شده",
    "dispatched": "ارسال/پردازش شده",
    "skipped": "رد شده",
    "pending": "در انتظار",

    # Orders
    "new": "جدید",
    "assigned": "تخصیص داده شده",
    "accepted": "پذیرفته شده",
    "in_progress": "در حال انجام",
    "started": "شروع شده",
    "completed": "تکمیل شده",
    "done": "انجام شده",
    "cancel_requested": "درخواست لغو",
    "rejected": "رد شده",

    # Invoices/payments
    "draft": "پیشنویس",
    "issued": "صادر شده",
    "paid": "پرداخت شده",
    "unpaid": "پرداخت نشده",
    "partially_paid": "پرداخت ناقص",
    "overdue": "سررسید گذشته",
    "refunded": "برگشت خورده",

    # Booleans / generic
    "true": "بله",
    "false": "خیر",
    "active": "فعال",
    "inactive": "غیرفعال",
}


@register.filter(name="fa_status")
def fa_status(value):
    if value is None:
        return "-"
    key = str(value).strip()
    if not key:
        return "-"
    return _STATUS_LABELS.get(key, _STATUS_LABELS.get(key.lower(), key))


# Backward-compatible aliases used by different templates
@register.filter(name="status_fa")
def status_fa(value):
    return fa_status(value)


@register.filter(name="sms_status_fa")
def sms_status_fa(value):
    return fa_status(value)


@register.filter(name="order_status_fa")
def order_status_fa(value):
    return fa_status(value)


@register.filter(name="invoice_status_fa")
def invoice_status_fa(value):
    return fa_status(value)


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
''', encoding="utf-8")


# Add {% load fa_labels %} to every template that uses these filters
filters = [
    "jalali_datetime",
    "jalali_date",
    "status_fa",
    "fa_status",
    "sms_status_fa",
    "order_status_fa",
    "invoice_status_fa",
    "fa_bool",
    "rial",
    "toman",
]

template_root = root / "templates"
changed = []

for path in template_root.rglob("*.html"):
    text = path.read_text(encoding="utf-8-sig")
    if not any(("|" + f) in text for f in filters):
        continue
    if "{% load fa_labels %}" in text:
        continue

    backup_path = backup_dir / (str(path.relative_to(root)).replace("\\", "__").replace("/", "__") + ".bak")
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path.write_text(text, encoding="utf-8")

    # If there are existing load tags after extends, append fa_labels to the first load tag.
    load_match = re.search(r"^\s*\{\%\s*load\s+([^%]+)\%\}\s*$", text, flags=re.MULTILINE)
    if load_match:
        old = load_match.group(0)
        if "fa_labels" not in old:
            new = old.replace("%}", " fa_labels %}")
            text = text.replace(old, new, 1)
    else:
        extends_match = re.match(r"(\s*\{\%\s*extends\s+[^%]+%\}\s*\r?\n)", text)
        if extends_match:
            text = text[:extends_match.end()] + "{% load fa_labels %}\n" + text[extends_match.end():]
        else:
            text = "{% load fa_labels %}\n" + text

    path.write_text(text, encoding="utf-8")
    changed.append(str(path.relative_to(root)))

print("fa_labels.py rewritten with all required filters.")
print("Templates updated:", len(changed))
for item in changed:
    print(" -", item)
print("Backup dir:", backup_dir)
