"""Message context and fallback builders for notification events."""
from __future__ import annotations

from django.conf import settings


def get_company_name(company) -> str:
    return getattr(company, "name", "") or getattr(company, "title", "") or getattr(company, "display_name", "") or "شرکت"


def get_public_base_url() -> str:
    return (
        getattr(settings, "PUBLIC_SITE_URL", "")
        or getattr(settings, "SITE_URL", "")
        or getattr(settings, "FRONTEND_URL", "")
        or "https://site.ir"
    ).rstrip("/")


def get_invoice_public_url(invoice) -> str:
    code = getattr(invoice, "public_code", "") or str(getattr(invoice, "id", ""))
    return f"{get_public_base_url()}/i/{code}/"


def build_order_context(order) -> dict:
    company = getattr(order, "company", None)
    technician = getattr(order, "technician", None)
    technician_user = getattr(technician, "user", None)

    return {
        "company_name": get_company_name(company),
        "company_code": getattr(company, "code", ""),
        "order_id": getattr(order, "id", ""),
        "customer_name": getattr(order, "customer_name", "") or getattr(order, "display_customer_name", ""),
        "customer_phone": getattr(order, "customer_phone", "") or getattr(order, "display_customer_phone", ""),
        "technician_name": (
            (technician_user.get_full_name() if technician_user and hasattr(technician_user, "get_full_name") else "")
            or getattr(technician_user, "full_name", "")
            or getattr(technician_user, "username", "")
            or ""
        ),
    }


def build_invoice_context(invoice) -> dict:
    company = getattr(invoice, "company", None)
    order = getattr(invoice, "order", None)
    customer_name = (
        getattr(invoice, "customer_name_snapshot", "")
        or getattr(order, "customer_name", "")
        or getattr(order, "display_customer_name", "")
        or ""
    )
    customer_phone = (
        getattr(invoice, "customer_phone_snapshot", "")
        or getattr(order, "customer_phone", "")
        or getattr(order, "display_customer_phone", "")
        or ""
    )
    return {
        "company_name": get_company_name(company),
        "company_code": getattr(company, "code", ""),
        "invoice_id": getattr(invoice, "id", ""),
        "invoice_number": getattr(invoice, "invoice_number", "") or getattr(invoice, "id", ""),
        "invoice_amount": getattr(invoice, "total_amount", 0),
        "public_invoice_url": get_invoice_public_url(invoice),
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "order_id": getattr(order, "id", ""),
    }



def build_company_context(company) -> dict:
    return {
        "company_name": get_company_name(company),
        "company_code": getattr(company, "code", ""),
    }


def build_user_context(user) -> dict:
    company = getattr(user, "company", None)
    return {
        "company_name": get_company_name(company),
        "company_code": getattr(company, "code", ""),
        "admin_name": getattr(user, "first_name", "") or getattr(user, "username", ""),
        "operator_name": getattr(user, "first_name", "") or getattr(user, "username", ""),
        "technician_name": getattr(user, "first_name", "") or getattr(user, "username", ""),
        "username": getattr(user, "username", ""),
        "phone_number": getattr(user, "phone", ""),
        "technician_phone": getattr(user, "phone", ""),
    }


def build_technician_context(technician) -> dict:
    user = getattr(technician, "user", None)
    data = build_user_context(user) if user is not None else {}
    data.update({
        "technician_name": (
            (user.get_full_name() if user and hasattr(user, "get_full_name") else "")
            or getattr(user, "username", "")
            or ""
        ),
        "technician_phone": getattr(user, "phone", "") if user else "",
        "new_status": "فعال" if getattr(technician, "is_available", False) else "غیرفعال",
        "service_wage_percent": getattr(technician, "service_wage_percent", ""),
        "goods_wage_percent": getattr(technician, "goods_wage_percent", ""),
        "travel_wage_percent": getattr(technician, "travel_wage_percent", ""),
    })
    return data


def build_service_category_context(category) -> dict:
    company = getattr(category, "company", None)
    return {
        "company_name": get_company_name(company),
        "company_code": getattr(company, "code", ""),
        "service_category": getattr(category, "title", ""),
        "category_title": getattr(category, "title", ""),
    }


def build_service_item_context(item) -> dict:
    company = getattr(item, "company", None)
    category = getattr(item, "category", None)
    return {
        "company_name": get_company_name(company),
        "company_code": getattr(company, "code", ""),
        "service_category": getattr(category, "title", ""),
        "item_title": getattr(item, "title", ""),
        "item_kind": getattr(item, "kind", ""),
    }

def build_context_for_event(event_key: str, target, payload: dict | None = None) -> dict:
    payload = payload or {}
    if target is None:
        return dict(payload)

    model_name = target.__class__.__name__.lower()
    if model_name == "invoice":
        context = build_invoice_context(target)
    elif model_name == "order":
        context = build_order_context(target)
    elif model_name == "company":
        context = build_company_context(target)
    elif model_name == "companyuser":
        context = build_user_context(target)
    elif model_name == "technician":
        context = build_technician_context(target)
    elif model_name == "companyservicecategory":
        context = build_service_category_context(target)
    elif model_name == "orderitemdefinition":
        context = build_service_item_context(target)
    else:
        context = {}

    context.update(payload)
    return context


def fallback_message_for_event(event_key: str, context: dict) -> str:
    company_name = context.get("company_name") or "شرکت"

    if event_key == "invoice_issued_customer":
        return f"فاکتور {context.get('invoice_number', '')} {company_name} صادر شد:\n{context.get('public_invoice_url', '')}"

    if event_key == "payment_success_customer":
        return f"پرداخت فاکتور {context.get('invoice_number', '')} با موفقیت ثبت شد."

    if event_key == "payment_failed_customer":
        return f"پرداخت فاکتور {context.get('invoice_number', '')} ناموفق بود."

    if event_key == "order_assigned_technician":
        return f"سفارش #{context.get('order_id', '')} به شما تخصیص داده شد."

    if event_key == "order_accepted_customer":
        return f"سفارش #{context.get('order_id', '')} توسط نیروی خدماتی پذیرفته شد."

    if event_key == "order_completed_customer":
        return f"سفارش #{context.get('order_id', '')} تکمیل شد."

    if event_key == "order_cancel_requested_admin":
        return f"درخواست لغو سفارش #{context.get('order_id', '')} ثبت شد."

    if event_key == "sms_credit_low_admin":
        return f"اعتبار پیامک {company_name} رو به اتمام است."

    if event_key == "sms_credit_empty_admin":
        return f"اعتبار پیامک {company_name} تمام شده است."

    if event_key == "subscription_expiring_admin":
        return f"اشتراک {company_name} در حال اتمام است."

    if event_key == "subscription_expired_admin":
        return f"اشتراک {company_name} به پایان رسیده است."

    if event_key == "platform_payment_success_admin":
        return f"پرداخت پلتفرمی {company_name} با موفقیت ثبت شد."

    if event_key == "order_available_technician":
        return f"سفارش جدید #{context.get('order_id', '')} برای بررسی در دسترس است."

    if event_key == "company_registered":
        return f"شرکت {context.get('company_name', company_name)} با کد {context.get('company_code', '')} ثبت شد."

    if event_key == "company_activated":
        return f"شرکت {context.get('company_name', company_name)} فعال شد."

    if event_key == "technician_created":
        return f"حساب نیروی خدماتی {context.get('technician_name', '')} در {company_name} ایجاد شد."

    if event_key == "operator_created":
        return f"حساب اپراتور {context.get('operator_name', '')} در {company_name} ایجاد شد."

    if event_key == "service_category_created":
        return f"رسته خدمات {context.get('service_category', '')} در {company_name} ایجاد شد."

    if event_key == "service_item_created":
        return f"آیتم خدمات {context.get('item_title', '')} در {company_name} ایجاد شد."

    if event_key == "order_started":
        return f"انجام سفارش #{context.get('order_id', '')} شروع شد."

    if event_key == "order_cancelled":
        return f"سفارش #{context.get('order_id', '')} لغو شد."

    if event_key == "order_cancel_approved_technician":
        return f"درخواست لغو سفارش #{context.get('order_id', '')} تایید شد."

    if event_key == "order_cancel_rejected_technician":
        return f"درخواست لغو سفارش #{context.get('order_id', '')} رد شد. لطفاً ادامه وضعیت سفارش را پیگیری کنید."

    return context.get("message") or f"رویداد {event_key}"
