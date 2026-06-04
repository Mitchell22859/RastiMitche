from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.contrib.auth import get_user_model
from django.http import HttpResponseForbidden
from django.urls import URLPattern, URLResolver, resolve
from django.utils.html import escape
from django.utils.text import slugify


AUTO_ALLOWED_OPERATOR_KEYS = {
    "home",
    "admin_home",
    "admin_dashboard",
}


def is_auto_allowed_operator_permission(permission_key: str) -> bool:
    return (permission_key or "") in AUTO_ALLOWED_OPERATOR_KEYS



@dataclass(frozen=True)
class OperatorPermissionItem:
    key: str
    title: str
    group: str
    path_template: str
    url_name: str
    description: str
    action_label: str


EXCLUDED_PERMISSION_PREFIXES = (
    "admin_operator_",
)

EXCLUDED_PERMISSION_NAMES = {
    "admin_operator_list",
    "admin_operator_create",
    "admin_operator_edit",
    "admin_operator_permissions",
}


SYNTHETIC_PERMISSION_ITEMS = [
    OperatorPermissionItem(
        key="admin_invoice_cancel",
        title="لغو فاکتور",
        group="فاکتورها",
        path_template="/{company_code}/admin/invoices/عملیات لغو",
        url_name="admin_invoice_cancel",
        description="اپراتور بتواند فاکتور را لغو کند. این دسترسی حساس است و از مشاهده فاکتور جداست.",
        action_label="لغو",
    ),
    OperatorPermissionItem(
        key="admin_invoice_edit",
        title="ویرایش یا تغییر وضعیت فاکتور",
        group="فاکتورها",
        path_template="/{company_code}/admin/invoices/عملیات ویرایش",
        url_name="admin_invoice_edit",
        description="اپراتور بتواند اطلاعات یا وضعیت فاکتور را تغییر دهد. این دسترسی از مشاهده فاکتور جداست.",
        action_label="ویرایش",
    ),
]


TITLE_MAP = {
    "admin_dashboard": "داشبورد ادمین",
    "admin_orders": "لیست و مدیریت سفارش‌ها",
    "admin_order_detail": "جزئیات سفارش",

    "admin_invoice_list": "مشاهده لیست فاکتورها",
    "admin_invoices": "مشاهده لیست فاکتورها",
    "invoice_list": "مشاهده لیست فاکتورها",
    "admin_invoice_detail": "مشاهده جزئیات فاکتور",
    "invoice_detail": "مشاهده جزئیات فاکتور",
    "admin_invoice_cancel": "لغو فاکتور",
    "invoice_cancel": "لغو فاکتور",
    "admin_invoice_create": "ساخت فاکتور",
    "invoice_create": "ساخت فاکتور",
    "admin_invoice_edit": "ویرایش یا تغییر وضعیت فاکتور",
    "invoice_edit": "ویرایش یا تغییر وضعیت فاکتور",

    "payment_list": "لیست پرداخت‌ها",
    "admin_payment_list": "لیست پرداخت‌ها",
    "payment_detail": "جزئیات پرداخت",
    "admin_payment_detail": "جزئیات پرداخت",

    "admin_company_settings": "تنظیمات اصلی سایت",
    "admin_notification_settings": "تنظیمات نوتیفیکیشن",

    "sms_template_list": "قالب‌های پیامک",
    "sms_template_create": "ساخت قالب پیامک",
    "sms_template_edit": "ویرایش قالب پیامک",
    "sms_template_toggle": "فعال/غیرفعال کردن قالب پیامک",
    "sms_outbox_list": "صندوق پیامک‌ها",
    "sms_diagnostics": "تشخیص و تست پیامک",

    "admin_base_data_dashboard": "داشبورد اطلاعات پایه",
    "admin_base_categories": "رسته‌های خدماتی و آیتم‌های سفارش",
    "admin_base_category_create": "ساخت رسته خدماتی",
    "admin_base_category_edit": "ویرایش رسته خدماتی",
    "admin_base_category_delete": "حذف رسته خدماتی",
    "admin_base_category_toggle_active": "فعال/غیرفعال کردن رسته خدماتی",
    "admin_order_item_create": "ساخت آیتم سفارش",
    "admin_order_item_edit": "ویرایش آیتم سفارش",
    "admin_order_item_delete": "غیرفعال کردن آیتم سفارش",

    "report_dashboard": "داشبورد گزارش‌ها",
    "admin_report_dashboard": "داشبورد گزارش‌ها",
}


DESCRIPTION_MAP = {
    "admin_dashboard": "اپراتور بتواند صفحه اصلی پنل ادمین شرکت را ببیند.",
    "admin_orders": "اپراتور بتواند لیست سفارش‌ها را مشاهده و پیگیری کند.",
    "admin_order_detail": "اپراتور بتواند وارد صفحه جزئیات هر سفارش شود.",

    "admin_invoice_list": "اپراتور فقط بتواند لیست فاکتورها را ببیند. این دسترسی اجازه لغو یا تغییر فاکتور نمی‌دهد.",
    "admin_invoices": "اپراتور فقط بتواند لیست فاکتورها را ببیند. این دسترسی اجازه لغو یا تغییر فاکتور نمی‌دهد.",
    "invoice_list": "اپراتور فقط بتواند لیست فاکتورها را ببیند. این دسترسی اجازه لغو یا تغییر فاکتور نمی‌دهد.",
    "admin_invoice_detail": "اپراتور فقط بتواند جزئیات فاکتور را ببیند. این دسترسی اجازه لغو یا تغییر فاکتور نمی‌دهد.",
    "invoice_detail": "اپراتور فقط بتواند جزئیات فاکتور را ببیند. این دسترسی اجازه لغو یا تغییر فاکتور نمی‌دهد.",
    "admin_invoice_cancel": "اپراتور بتواند فاکتور را لغو کند. این دسترسی حساس است و از مشاهده فاکتور جداست.",
    "invoice_cancel": "اپراتور بتواند فاکتور را لغو کند. این دسترسی حساس است و از مشاهده فاکتور جداست.",
    "admin_invoice_create": "اپراتور بتواند فاکتور جدید بسازد.",
    "invoice_create": "اپراتور بتواند فاکتور جدید بسازد.",
    "admin_invoice_edit": "اپراتور بتواند فاکتور را ویرایش کند یا وضعیت آن را تغییر دهد.",
    "invoice_edit": "اپراتور بتواند فاکتور را ویرایش کند یا وضعیت آن را تغییر دهد.",

    "payment_list": "اپراتور بتواند لیست پرداخت‌ها را مشاهده کند.",
    "admin_payment_list": "اپراتور بتواند لیست پرداخت‌ها را مشاهده کند.",
    "payment_detail": "اپراتور بتواند جزئیات پرداخت را مشاهده کند.",
    "admin_payment_detail": "اپراتور بتواند جزئیات پرداخت را مشاهده کند.",

    "admin_company_settings": "اپراتور بتواند تنظیمات اصلی سایت شرکت را مشاهده یا تغییر دهد.",
    "admin_notification_settings": "اپراتور بتواند تنظیمات ارسال نوتیفیکیشن و پیامک را تغییر دهد.",

    "sms_template_list": "اپراتور بتواند قالب‌های پیامک را مشاهده کند.",
    "sms_template_create": "اپراتور بتواند قالب پیامک جدید بسازد.",
    "sms_template_edit": "اپراتور بتواند متن و تنظیمات قالب‌های پیامک را ویرایش کند.",
    "sms_template_toggle": "اپراتور بتواند قالب پیامک را فعال یا غیرفعال کند.",
    "sms_outbox_list": "اپراتور بتواند پیامک‌های ساخته‌شده و وضعیت ارسال آن‌ها را ببیند.",
    "sms_diagnostics": "اپراتور بتواند ابزار بررسی و تست پیامک را اجرا کند.",

    "admin_base_data_dashboard": "اپراتور بتواند داشبورد اطلاعات پایه را ببیند.",
    "admin_base_categories": "اپراتور بتواند رسته‌های خدماتی و آیتم‌های سفارش را ببیند.",
    "admin_base_category_create": "اپراتور بتواند رسته خدماتی جدید تعریف کند.",
    "admin_base_category_edit": "اپراتور بتواند عنوان و تنظیمات رسته خدماتی را ویرایش کند.",
    "admin_base_category_delete": "اپراتور بتواند رسته خدماتی را حذف واقعی کند.",
    "admin_base_category_toggle_active": "اپراتور بتواند رسته خدماتی را فعال یا غیرفعال کند.",
    "admin_order_item_create": "اپراتور بتواند آیتم سفارش جدید برای رسته‌ها بسازد.",
    "admin_order_item_edit": "اپراتور بتواند آیتم‌های سفارش را ویرایش کند.",
    "admin_order_item_delete": "اپراتور بتواند آیتم سفارش را غیرفعال کند.",
}


def get_staff_role_value():
    try:
        from apps.accounts.models import UserRole

        if hasattr(UserRole, "COMPANY_STAFF"):
            return UserRole.COMPANY_STAFF
        if hasattr(UserRole, "OPERATOR"):
            return UserRole.OPERATOR
    except Exception:
        pass
    return "company_staff"


def get_admin_role_value():
    try:
        from apps.accounts.models import UserRole

        if hasattr(UserRole, "COMPANY_ADMIN"):
            return UserRole.COMPANY_ADMIN
    except Exception:
        pass
    return "company_admin"


def role_text(user) -> str:
    return str(getattr(user, "role", "") or "").strip().lower()


def model_has_field(model, field_name: str) -> bool:
    try:
        model._meta.get_field(field_name)
        return True
    except Exception:
        return False


def get_login_field_name(model) -> str:
    for field_name in ("phone", "username", "email"):
        if model_has_field(model, field_name):
            return field_name
    return getattr(model, "USERNAME_FIELD", "username")


def set_if_field(obj, field_name: str, value) -> None:
    if model_has_field(obj.__class__, field_name):
        setattr(obj, field_name, value)


def set_user_display_name(user, display_name: str) -> None:
    display_name = (display_name or "").strip()

    set_if_field(user, "full_name", display_name)
    set_if_field(user, "name", display_name)

    if model_has_field(user.__class__, "first_name"):
        parts = display_name.split()
        first_name = parts[0] if parts else ""
        last_name = " ".join(parts[1:]) if len(parts) > 1 else ""
        setattr(user, "first_name", first_name)
        if model_has_field(user.__class__, "last_name"):
            setattr(user, "last_name", last_name)
    elif model_has_field(user.__class__, "last_name"):
        setattr(user, "last_name", display_name)


def get_user_display(user) -> str:
    for attr in ("full_name", "name"):
        value = getattr(user, attr, "")
        if value:
            return str(value)

    try:
        full_name = user.get_full_name()
        if full_name:
            return full_name
    except Exception:
        pass

    for attr in ("phone", "username", "email"):
        value = getattr(user, attr, "")
        if value:
            return str(value)

    return f"User #{user.pk}"


def get_user_identifier(user) -> str:
    for attr in ("phone", "username", "email"):
        value = getattr(user, attr, "")
        if value:
            return str(value)
    return str(user.pk)


def get_operator_queryset(company):
    User = get_user_model()
    qs = User.objects.all()

    if model_has_field(User, "company"):
        qs = qs.filter(company=company)

    if model_has_field(User, "role"):
        qs = qs.filter(role=get_staff_role_value())

    return qs.order_by("id")


def re_sub_converter(path: str) -> str:
    import re

    path = re.sub(r"<[^:>]+:([^>]+)>", r"{\1}", path)
    path = re.sub(r"<([^>]+)>", r"{\1}", path)
    return path


def make_route_path(route_text: str) -> str:
    path = str(route_text)
    path = path.replace("^", "").replace("$", "")
    path = re_sub_converter(path)
    if not path.startswith("/"):
        path = "/" + path
    return path


def group_for_route(route: str, name: str) -> str:
    text = f"{route} {name}".lower()
    if "invoice" in text:
        return "فاکتورها"
    if "payment" in text:
        return "پرداخت‌ها"
    if "sms" in text:
        return "پیامک"
    if "notification" in text:
        return "نوتیفیکیشن"
    if "base-data" in text or "base_" in text or "category" in text or "item" in text:
        return "اطلاعات پایه"
    if "order" in text:
        return "سفارش‌ها"
    if "report" in text:
        return "گزارش‌ها"
    if "setting" in text:
        return "تنظیمات"
    return "عمومی"


def action_label_for_permission(name: str, route: str) -> str:
    text = f"{name} {route}".lower()
    if "cancel" in text:
        return "لغو"
    if "delete" in text or "remove" in text:
        return "حذف"
    if "create" in text or "add" in text:
        return "افزودن"
    if "edit" in text or "update" in text or "modify" in text:
        return "ویرایش"
    if "toggle" in text or "active" in text:
        return "فعال/غیرفعال"
    if "detail" in text:
        return "مشاهده جزئیات"
    if "list" in text or "dashboard" in text or "invoices" in text:
        return "مشاهده"
    return "دسترسی"


def title_for_permission(name: str, route: str) -> str:
    if name in TITLE_MAP:
        return TITLE_MAP[name]

    text = f"{name} {route}".lower()
    action = action_label_for_permission(name, route)

    if "invoice" in text:
        return f"{action} فاکتور"
    if "payment" in text:
        return f"{action} پرداخت"
    if "order" in text:
        return f"{action} سفارش"
    if "sms" in text:
        return f"{action} پیامک"
    if "setting" in text:
        return f"{action} تنظیمات"

    raw = (name or route or "").replace("_", " ").replace("-", " ").strip()
    return raw or "دسترسی"


def description_for_permission(name: str, route: str) -> str:
    if name in DESCRIPTION_MAP:
        return DESCRIPTION_MAP[name]

    action = action_label_for_permission(name, route)
    group = group_for_route(route, name)
    path = make_route_path(route)
    return f"اجازه {action} در بخش {group}. مسیر مربوطه: {path}"


def should_include_admin_route(route: str, name: str) -> bool:
    route_lower = str(route).lower()
    name_lower = str(name or "").lower()

    if "admin/" not in route_lower:
        return False

    if name_lower in EXCLUDED_PERMISSION_NAMES:
        return False

    if any(name_lower.startswith(prefix) for prefix in EXCLUDED_PERMISSION_PREFIXES):
        return False

    if "login" in route_lower or "logout" in route_lower:
        return False

    return True


def iter_url_patterns(patterns: Iterable, prefix: str = ""):
    for pattern in patterns:
        if isinstance(pattern, URLPattern):
            route = prefix + str(pattern.pattern)
            yield route, pattern.name or ""
        elif isinstance(pattern, URLResolver):
            nested_prefix = prefix + str(pattern.pattern)
            yield from iter_url_patterns(pattern.url_patterns, nested_prefix)


def list_operator_permission_items() -> list[OperatorPermissionItem]:
    try:
        from apps.tenants.urls import urlpatterns
    except Exception:
        return []

    items = []
    seen = set()

    for item in SYNTHETIC_PERMISSION_ITEMS:
        items.append(item)
        seen.add(item.key)

    for route, name in iter_url_patterns(urlpatterns):
        if not should_include_admin_route(route, name):
            continue

        key = name or slugify(route) or route.replace("/", "_")
        if not key or key in seen:
            continue
        seen.add(key)

        items.append(
            OperatorPermissionItem(
                key=key,
                title=title_for_permission(name, route),
                group=group_for_route(route, name),
                path_template="/{company_code}/" + make_route_path(route).lstrip("/"),
                url_name=name,
                description=description_for_permission(name, route),
                action_label=action_label_for_permission(name, route),
            )
        )

    return sorted(items, key=lambda item: (item.group, item.title, item.key))


def grouped_permission_items() -> dict[str, list[OperatorPermissionItem]]:
    grouped: dict[str, list[OperatorPermissionItem]] = {}
    for item in list_operator_permission_items():
        grouped.setdefault(item.group, []).append(item)
    return grouped


def is_company_admin(user) -> bool:
    if getattr(user, "is_superuser", False):
        return True

    role = role_text(user)
    admin_role = str(get_admin_role_value()).strip().lower()

    return role in {
        admin_role,
        "company_admin",
        "company admin",
        "admin",
        "tenant_admin",
        "owner",
    }


def get_company_from_request(request):
    company = getattr(request, "company", None)
    if company is not None:
        return company

    try:
        match = resolve(request.path_info)
        code = (
            match.kwargs.get("company_code")
            or match.kwargs.get("tenant_code")
            or match.kwargs.get("company")
            or ""
        )
    except Exception:
        code = ""

    if not code:
        parts = [part for part in request.path_info.split("/") if part]
        if parts:
            code = parts[0]

    if not code:
        return None

    try:
        from apps.tenants.models import Company

        return Company.objects.filter(code=code).first()
    except Exception:
        return None


def is_company_admin_path(request, company) -> bool:
    if company is not None:
        return request.path.startswith(f"/{company.code}/admin/")

    parts = [part for part in request.path_info.split("/") if part]
    return len(parts) >= 2 and parts[1] == "admin"


def get_resolved_permission_key_for_request(request) -> str:
    try:
        match = resolve(request.path_info)
    except Exception:
        return ""

    return match.url_name or match.view_name or ""


def request_text_values(request) -> str:
    values = []
    try:
        values.extend([str(v) for v in request.POST.values()])
        values.extend([str(k) for k in request.POST.keys()])
    except Exception:
        pass
    return " ".join(values).lower()


def get_effective_permission_key_for_request(request) -> str:
    """
    Converts broad page access into stricter action access.

    Example:
    - GET /n54/admin/invoices/ -> admin_invoices
    - POST /n54/admin/invoices/ with action=cancel -> admin_invoice_cancel
    - POST /n54/admin/invoices/<id>/cancel/ -> admin_invoice_cancel
    """
    path = request.path_info.lower()
    resolved_key = get_resolved_permission_key_for_request(request)

    if "/admin/invoices" in path or "invoice" in (resolved_key or "").lower():
        if request.method.upper() == "POST":
            posted = request_text_values(request)
            if (
                "cancel" in path
                or "cancel" in posted
                or "لغو" in posted
                or "void" in posted
                or "cancelled" in posted
                or "canceled" in posted
            ):
                return "admin_invoice_cancel"

            if (
                "delete" in path
                or "remove" in path
                or "delete" in posted
                or "remove" in posted
                or "حذف" in posted
            ):
                return "admin_invoice_edit"

            if (
                "edit" in path
                or "update" in path
                or "status" in posted
                or "amount" in posted
                or "price" in posted
                or "invoice" in posted
            ):
                return "admin_invoice_edit"

            # Any invoice POST is considered a modification unless explicitly mapped otherwise.
            return "admin_invoice_edit"

    return resolved_key


def operator_has_permission(*, company, operator, permission_key: str) -> bool:
    if not permission_key:
        return False

    from apps.accounts.models import OperatorPermission

    return OperatorPermission.objects.filter(
        company=company,
        operator=operator,
        permission_key=permission_key,
        is_allowed=True,
    ).exists()


def permission_denied_response(request, *, permission_key: str = "", title: str = ""):
    path = escape(request.path)
    permission_key = escape(permission_key or "نامشخص")
    title = escape(title or "دسترسی به این بخش برای حساب شما فعال نشده است.")

    html = f"""
<!doctype html>
<html lang="fa" dir="rtl">
<head>
    <meta charset="utf-8">
    <title>دسترسی ندارید</title>
    <style>
        body {{
            font-family: Tahoma, Arial, sans-serif;
            background: #f8fafc;
            color: #0f172a;
            margin: 0;
            padding: 2rem;
        }}
        .box {{
            max-width: 760px;
            margin: 3rem auto;
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 18px;
            padding: 1.5rem;
            box-shadow: 0 12px 32px rgba(15,23,42,.08);
        }}
        h1 {{
            margin-top: 0;
            color: #b91c1c;
            font-size: 1.45rem;
        }}
        .muted {{
            color: #64748b;
            line-height: 1.9;
        }}
        code {{
            direction: ltr;
            display: inline-block;
            background: #f1f5f9;
            padding: .25rem .45rem;
            border-radius: .5rem;
        }}
        .actions {{
            margin-top: 1rem;
            display: flex;
            gap: .5rem;
            flex-wrap: wrap;
        }}
        a, button {{
            border: 0;
            border-radius: .75rem;
            padding: .7rem 1rem;
            text-decoration: none;
            cursor: pointer;
            font: inherit;
        }}
        .primary {{
            background: #2563eb;
            color: white;
        }}
        .secondary {{
            background: #e2e8f0;
            color: #0f172a;
        }}
    </style>
</head>
<body>
    <div class="box">
        <h1>شما اجازه دسترسی به این بخش را ندارید</h1>
        <p class="muted">{title}</p>
        <p class="muted">
            این حساب کاربری اپراتور است و مدیر شرکت باید دسترسی این بخش را برای شما فعال کند.
        </p>
        <p>مسیر درخواستی: <code>{path}</code></p>
        <p>کلید دسترسی: <code>{permission_key}</code></p>
        <div class="actions">
            <button class="primary" onclick="history.back()">بازگشت</button>
            <a class="secondary" href="/">صفحه اصلی</a>
        </div>
    </div>
</body>
</html>
"""
    return HttpResponseForbidden(html)


class OperatorPermissionMiddleware:
    """
    Enforces page-level and action-level permissions for all non-admin authenticated users on company admin pages.

    Critical behavior:
    - Company admins and superusers bypass.
    - Every authenticated non-admin user under /<company>/admin/ is denied by default.
    - Exact route permission is required for GET.
    - POST actions such as invoice cancel are mapped to action-specific permissions.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)

        if not user or not getattr(user, "is_authenticated", False):
            return self.get_response(request)

        company = get_company_from_request(request)
        if not is_company_admin_path(request, company):
            return self.get_response(request)

        if is_company_admin(user):
            return self.get_response(request)

        if company is None:
            return permission_denied_response(
                request,
                permission_key="company_not_found",
                title="شرکت مربوط به این آدرس پیدا نشد.",
            )

        permission_key = get_effective_permission_key_for_request(request)

        if not permission_key:
            return permission_denied_response(
                request,
                permission_key="unknown_route",
                title="برای این صفحه کلید دسترسی تعریف نشده است، بنابراین دسترسی اپراتور بسته است.",
            )

        if not getattr(user, "is_active", True):
            return permission_denied_response(
                request,
                permission_key="inactive_operator",
                title="حساب کاربری شما غیرفعال است. برای ورود، مدیر شرکت باید حساب شما را فعال کند.",
            )

        if is_auto_allowed_operator_permission(permission_key):
            return self.get_response(request)

        if operator_has_permission(company=company, operator=user, permission_key=permission_key):
            return self.get_response(request)

        return permission_denied_response(
            request,
            permission_key=permission_key,
            title="دسترسی لازم برای ورود به این صفحه یا انجام این عملیات برای شما فعال نشده است.",
        )
