
from __future__ import annotations

import re
import shutil
from pathlib import Path
from datetime import datetime

root = Path.cwd()
if not (root / "manage.py").exists():
    raise SystemExit("manage.py not found. Run this from current_project or let the PS script cd there.")

backup_dir = root / "patch_backups" / ("admin_status_dashboard_orders_6h_" + datetime.now().strftime("%Y%m%d_%H%M%S"))
backup_dir.mkdir(parents=True, exist_ok=True)

def backup(path: Path) -> None:
    if not path.exists():
        return
    rel = path.relative_to(root)
    dst = backup_dir / str(rel).replace("\\", "__").replace("/", "__")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(path, dst)

tag_dir = root / "apps" / "common" / "templatetags"
tag_dir.mkdir(parents=True, exist_ok=True)
(tag_dir / "__init__.py").write_text("", encoding="utf-8")

fa_labels_path = tag_dir / "fa_labels.py"
backup(fa_labels_path)

fa_labels_source = '''
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
    "queued": "\\u062f\\u0631 \\u0635\\u0641 \\u0627\\u0631\\u0633\\u0627\\u0644",
    "sending": "\\u062f\\u0631 \\u062d\\u0627\\u0644 \\u0627\\u0631\\u0633\\u0627\\u0644",
    "sent": "\\u0627\\u0631\\u0633\\u0627\\u0644 \\u0634\\u062f\\u0647",
    "delivered": "\\u062a\\u062d\\u0648\\u06cc\\u0644 \\u0634\\u062f\\u0647",
    "failed": "\\u0627\\u0631\\u0633\\u0627\\u0644 \\u0646\\u0627\\u0645\\u0648\\u0641\\u0642",

    "recorded": "\\u062b\\u0628\\u062a \\u0634\\u062f\\u0647",
    "dispatched": "\\u067e\\u0631\\u062f\\u0627\\u0632\\u0634 \\u0634\\u062f\\u0647",
    "skipped": "\\u0631\\u062f \\u0634\\u062f\\u0647",
    "pending": "\\u062f\\u0631 \\u0627\\u0646\\u062a\\u0638\\u0627\\u0631",

    "new": "\\u062c\\u062f\\u06cc\\u062f",
    "assigned": "\\u062a\\u062e\\u0635\\u06cc\\u0635 \\u062f\\u0627\\u062f\\u0647 \\u0634\\u062f\\u0647",
    "accepted": "\\u067e\\u0630\\u06cc\\u0631\\u0641\\u062a\\u0647 \\u0634\\u062f\\u0647",
    "in_progress": "\\u062f\\u0631 \\u062d\\u0627\\u0644 \\u0627\\u0646\\u062c\\u0627\\u0645",
    "started": "\\u0634\\u0631\\u0648\\u0639 \\u0634\\u062f\\u0647",
    "completed": "\\u062a\\u06a9\\u0645\\u06cc\\u0644 \\u0634\\u062f\\u0647",
    "done": "\\u0627\\u0646\\u062c\\u0627\\u0645 \\u0634\\u062f\\u0647",
    "cancelled": "\\u0644\\u063a\\u0648 \\u0634\\u062f\\u0647",
    "canceled": "\\u0644\\u063a\\u0648 \\u0634\\u062f\\u0647",
    "cancel_requested": "\\u062f\\u0631\\u062e\\u0648\\u0627\\u0633\\u062a \\u0644\\u063a\\u0648",
    "rejected": "\\u0631\\u062f \\u0634\\u062f\\u0647",

    "draft": "\\u067e\\u06cc\\u0634\\u200c\\u0646\\u0648\\u06cc\\u0633",
    "issued": "\\u0635\\u0627\\u062f\\u0631 \\u0634\\u062f\\u0647",
    "paid": "\\u067e\\u0631\\u062f\\u0627\\u062e\\u062a \\u0634\\u062f\\u0647",
    "unpaid": "\\u067e\\u0631\\u062f\\u0627\\u062e\\u062a \\u0646\\u0634\\u062f\\u0647",
    "partially_paid": "\\u067e\\u0631\\u062f\\u0627\\u062e\\u062a \\u0646\\u0627\\u0642\\u0635",
    "overdue": "\\u0633\\u0631\\u0631\\u0633\\u06cc\\u062f \\u06af\\u0630\\u0634\\u062a\\u0647",
    "refunded": "\\u0628\\u0631\\u06af\\u0634\\u062a \\u062e\\u0648\\u0631\\u062f\\u0647",

    "true": "\\u0628\\u0644\\u0647",
    "false": "\\u062e\\u06cc\\u0631",
    "active": "\\u0641\\u0639\\u0627\\u0644",
    "inactive": "\\u063a\\u06cc\\u0631\\u0641\\u0639\\u0627\\u0644",
}


def _normalize_status_key(value):
    key = str(value).strip()
    return key.replace("-", "_").replace(" ", "_").lower()


@register.filter(name="fa_status")
def fa_status(value):
    if value is None:
        return "-"
    key = str(value).strip()
    if not key:
        return "-"
    return _STATUS_LABELS.get(key) or _STATUS_LABELS.get(_normalize_status_key(key)) or key


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
    return "\\u0628\\u0644\\u0647" if bool(value) else "\\u062e\\u06cc\\u0631"


@register.filter(name="rial")
def rial(value):
    try:
        return f"{int(value):,} \\u0631\\u06cc\\u0627\\u0644"
    except Exception:
        return str(value)


@register.filter(name="toman")
def toman(value):
    try:
        return f"{int(value):,} \\u062a\\u0648\\u0645\\u0627\\u0646"
    except Exception:
        return str(value)
'''
fa_labels_path.write_text(fa_labels_source, encoding="utf-8")


def ensure_load_fa_labels(text: str) -> str:
    if "{% load fa_labels" in text:
        return text

    m = re.search(r"^\s*\{\%\s*load\s+([^%]+)\%\}\s*$", text, flags=re.MULTILINE)
    if m:
        old = m.group(0)
        if "fa_labels" not in old:
            return text.replace(old, old.replace("%}", " fa_labels %}"), 1)
        return text

    m = re.match(r"(\s*\{\%\s*extends\s+[^%]+%\}\s*\r?\n)", text)
    if m:
        return text[:m.end()] + "{% load fa_labels %}\n" + text[m.end():]
    return "{% load fa_labels %}\n" + text


def patch_template(path: Path) -> bool:
    if not path.exists():
        return False
    original = path.read_text(encoding="utf-8-sig")
    text = original

    text = text.replace("Technician:", "\\u0646\\u06cc\\u0631\\u0648\\u06cc \\u062e\\u062f\\u0645\\u0627\\u062a\\u06cc:")
    text = text.replace(":Technician", ":\\u0646\\u06cc\\u0631\\u0648\\u06cc \\u062e\\u062f\\u0645\\u0627\\u062a\\u06cc")

    replacements = {
        r"\{\{\s*order\.status\s*\}\}": "{{ order.status|status_fa }}",
        r"\{\{\s*order\.status\|title\s*\}\}": "{{ order.status|status_fa }}",
        r"\{\{\s*order\.get_status_display\s*\}\}": "{{ order.status|status_fa }}",
        r"\{\{\s*order\.get_status_display\|default:order\.status\s*\}\}": "{{ order.status|status_fa }}",

        r"\{\{\s*recent\.status\s*\}\}": "{{ recent.status|status_fa }}",
        r"\{\{\s*recent\.status\|title\s*\}\}": "{{ recent.status|status_fa }}",
        r"\{\{\s*recent\.get_status_display\s*\}\}": "{{ recent.status|status_fa }}",

        r"\{\{\s*inv\.status\s*\}\}": "{{ inv.status|status_fa }}",
        r"\{\{\s*inv\.status\|title\s*\}\}": "{{ inv.status|status_fa }}",
        r"\{\{\s*inv\.get_status_display\s*\}\}": "{{ inv.status|status_fa }}",
        r"\{\{\s*inv\.get_status_display\|default:inv\.status\s*\}\}": "{{ inv.status|status_fa }}",

        r"\{\{\s*invoice\.status\s*\}\}": "{{ invoice.status|status_fa }}",
        r"\{\{\s*invoice\.status\|title\s*\}\}": "{{ invoice.status|status_fa }}",
        r"\{\{\s*invoice\.get_status_display\s*\}\}": "{{ invoice.status|status_fa }}",
        r"\{\{\s*invoice\.get_status_display\|default:invoice\.status\s*\}\}": "{{ invoice.status|status_fa }}",
    }

    for pat, repl in replacements.items():
        text = re.sub(pat, repl, text)

    text = re.sub(r'\{\{\s*([^{}|]+?)\s*\|\s*date:"Y/m/d H:i"\s*\}\}', r'{{ \1|jalali_datetime }}', text)
    text = re.sub(r'\{\{\s*([^{}|]+?)\s*\|\s*date:"Y/m/d H:i:s"\s*\}\}', r'{{ \1|jalali_datetime }}', text)
    text = re.sub(r'\{\{\s*([^{}|]+?)\s*\|\s*date:"Y/m/d"\s*\}\}', r'{{ \1|jalali_date }}', text)

    if text != original:
        text = ensure_load_fa_labels(text)
        backup(path)
        path.write_text(text, encoding="utf-8")
        return True
    return False


targets = [
    root / "templates" / "dashboard" / "home.html",
    root / "templates" / "tenants" / "admin_orders.html",
    root / "templates" / "tenants" / "admin_invoices.html",
    root / "templates" / "tenants" / "admin_invoice_detail.html",
    root / "templates" / "tenants" / "admin_order_detail.html",
]

changed = []
for t in targets:
    if patch_template(t):
        changed.append(str(t.relative_to(root)))

remaining = []
for path in (root / "templates").rglob("*.html"):
    text = path.read_text(encoding="utf-8-sig")
    for i, line in enumerate(text.splitlines(), start=1):
        if (
            re.search(r"\{\{\s*[^{}]*\.(status|get_status_display)\s*(?:\}\}|\|title)", line)
            or 'date:"Y/m/d' in line
            or "Technician:" in line
        ):
            remaining.append(f"{path.relative_to(root)}:{i}: {line.strip()}")

report_path = backup_dir / "admin_status_dashboard_orders_6h_report.txt"
report_path.write_text("\n".join(remaining), encoding="utf-8")

print("fa_labels.py rewritten cleanly.")
print("Templates changed:", len(changed))
for item in changed:
    print(" -", item)
print("Backup dir:", backup_dir)
print("Remaining report:", report_path)
print("Remaining suspect lines:", len(remaining))
