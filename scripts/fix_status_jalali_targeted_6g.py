from __future__ import annotations

import re
from pathlib import Path

ROOT = Path.cwd()
BACKUP_DIR = ROOT / "patch_backups" / "status_jalali_targeted_fix_6g"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)

TAG_DIR = ROOT / "apps" / "common" / "templatetags"
TAG_DIR.mkdir(parents=True, exist_ok=True)
(TAG_DIR / "__init__.py").write_text("", encoding="utf-8")

FA_LABELS = TAG_DIR / "fa_labels.py"
if FA_LABELS.exists():
    (BACKUP_DIR / "fa_labels.py.bak").write_text(FA_LABELS.read_text(encoding="utf-8-sig"), encoding="utf-8")

fa_labels_code = r"""
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
    "queued": "در صف ارسال",
    "sending": "در حال ارسال",
    "sent": "ارسال شده",
    "delivered": "تحویل شده",
    "failed": "ارسال ناموفق",
    "cancelled": "لغو شده",
    "canceled": "لغو شده",

    "recorded": "ثبت شده",
    "dispatched": "پردازش شده",
    "skipped": "رد شده",
    "pending": "در انتظار",

    "new": "جدید",
    "assigned": "تخصیص داده شده",
    "accepted": "پذیرفته شده",
    "in_progress": "در حال انجام",
    "started": "شروع شده",
    "completed": "تکمیل شده",
    "done": "انجام شده",
    "cancel_requested": "درخواست لغو",
    "cancelled_by_customer": "لغو شده توسط مشتری",
    "cancelled_by_admin": "لغو شده توسط مدیر",
    "cancelled_by_technician": "لغو شده توسط نیروی خدماتی",
    "rejected": "رد شده",

    "draft": "پیش‌نویس",
    "issued": "صادر شده",
    "paid": "پرداخت شده",
    "unpaid": "پرداخت نشده",
    "partially_paid": "پرداخت ناقص",
    "overdue": "سررسید گذشته",
    "refunded": "برگشت خورده",
    "cancelled_invoice": "فاکتور لغو شده",

    "true": "بله",
    "false": "خیر",
    "active": "فعال",
    "inactive": "غیرفعال",
}


def _normalize(value):
    if value is None:
        return ""
    return str(value).strip()


@register.filter(name="fa_status")
def fa_status(value):
    key = _normalize(value)
    if not key:
        return "-"
    lower = key.lower()
    return _STATUS_LABELS.get(lower, _STATUS_LABELS.get(key, key))


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


@register.filter(name="payment_status_fa")
def payment_status_fa(value):
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
"""
FA_LABELS.write_text(fa_labels_code, encoding="utf-8")


def backup(path: Path):
    rel = str(path.relative_to(ROOT)).replace("\\", "__").replace("/", "__")
    (BACKUP_DIR / (rel + ".bak")).write_text(path.read_text(encoding="utf-8-sig"), encoding="utf-8")


def ensure_load(text: str) -> str:
    if "{% load fa_labels %}" in text:
        return text
    load_match = re.search(r"^\s*\{\%\s*load\s+([^%]+)\%\}\s*$", text, flags=re.MULTILINE)
    if load_match:
        old = load_match.group(0)
        if "fa_labels" not in old:
            return text.replace(old, old.replace("%}", " fa_labels %}"), 1)
        return text
    extends_match = re.match(r"(\s*\{\%\s*extends\s+[^%]+%\}\s*\r?\n)", text)
    if extends_match:
        return text[:extends_match.end()] + "{% load fa_labels %}\n" + text[extends_match.end():]
    return "{% load fa_labels %}\n" + text


def apply_common_replacements(text: str) -> str:
    text = text.replace("Technician:", "نیروی خدماتی:")
    text = text.replace("Technician :", "نیروی خدماتی:")

    # get_status_display may return English labels such as Done/Paid.
    text = re.sub(
        r"\{\{\s*([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*\.get_status_display)\s*\|\s*title\s*\}\}",
        r"{{ \1|status_fa }}",
        text,
    )
    text = re.sub(
        r"\{\{\s*([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*\.get_status_display)\s*\}\}",
        r"{{ \1|status_fa }}",
        text,
    )

    # Raw .status and .status|title/default.
    text = re.sub(
        r"\{\{\s*([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*\.status)\s*\|\s*title\s*\}\}",
        r"{{ \1|status_fa }}",
        text,
    )
    text = re.sub(
        r"\{\{\s*([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*\.status)\s*\|\s*default:[^}]+\}\}",
        r"{{ \1|status_fa }}",
        text,
    )
    text = re.sub(
        r"\{\{\s*([A-Za-z_][\w]*(?:\.[A-Za-z_][\w]*)*\.status)\s*\}\}",
        r"{{ \1|status_fa }}",
        text,
    )

    # Date filters.
    text = re.sub(
        r"\{\{\s*([^{}|]+?)\s*\|\s*date\s*:\s*[\"']Y/m/d H:i[\"']\s*\}\}",
        r"{{ \1|jalali_datetime }}",
        text,
    )
    text = re.sub(
        r"\{\{\s*([^{}|]+?)\s*\|\s*date\s*:\s*[\"']Y/m/d[\"']\s*\}\}",
        r"{{ \1|jalali_date }}",
        text,
    )
    text = re.sub(
        r"\{\{\s*([^{}|]+?)\s*\|\s*date\s*:\s*[\"']Y-m-d[\"']\s*\}\}",
        r"{{ \1|jalali_date }}",
        text,
    )
    return text


changed = []
for path in (ROOT / "templates").rglob("*.html"):
    original = path.read_text(encoding="utf-8-sig")
    text = original

    if any(x in text for x in [".status", "get_status_display", 'date:"Y/m/d"', "date:'Y/m/d'", 'date:"Y-m-d"', "Technician:"]):
        text = apply_common_replacements(text)

    if any(f in text for f in ["|status_fa", "|fa_status", "|jalali_date", "|jalali_datetime", "|order_status_fa", "|invoice_status_fa"]):
        text = ensure_load(text)

    if text != original:
        backup(path)
        path.write_text(text, encoding="utf-8")
        changed.append(str(path.relative_to(ROOT)))


# Extra direct fixes for known pages if patterns were missed.
known_files = [
    ROOT / "templates" / "dashboard" / "home.html",
    ROOT / "templates" / "tenants" / "admin_orders.html",
    ROOT / "templates" / "tenants" / "admin_invoices.html",
]
for path in known_files:
    if not path.exists():
        continue
    original = path.read_text(encoding="utf-8-sig")
    text = ensure_load(apply_common_replacements(original))
    if text != original:
        backup(path)
        path.write_text(text, encoding="utf-8")
        if str(path.relative_to(ROOT)) not in changed:
            changed.append(str(path.relative_to(ROOT)))

report = BACKUP_DIR / "status_jalali_targeted_fix_6g_report.txt"
remaining = []
for path in (ROOT / "templates").rglob("*.html"):
    text = path.read_text(encoding="utf-8-sig")
    if any(x in text for x in [
        "{{ order.status", "{{ inv.status", "{{ invoice.status",
        "{{ order.get_status_display", "{{ inv.get_status_display", "{{ invoice.get_status_display",
        'date:"Y/m/d"', 'date:"Y-m-d"', "Technician:"
    ]):
        remaining.append(str(path.relative_to(ROOT)))

report.write_text(
    "Changed files:\n" + "\n".join(changed) + "\n\nRemaining suspicious files:\n" + "\n".join(remaining) + "\n",
    encoding="utf-8",
)

print("fa_labels.py rewritten cleanly.")
print("Changed templates:", len(changed))
for p in changed:
    print(" -", p)
print("Report:", report)
