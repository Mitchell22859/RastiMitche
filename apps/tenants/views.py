"""
Tenants - Views.

Public page views and service request submission.
All business logic delegated to services/selectors.
"""
import re

from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.notifications.services import NotificationEventHooks
from apps.orders.models import Order
from apps.sms.services import SMSEventHooks

from .forms import ServiceRequestForm
from .models import ServiceRequest
from .selectors import (
    CompanyGallerySelector,
    CompanyPageSelector,
    CompanyServiceSelector,
)
from .services import ServiceRequestCreateService


def company_home(request: HttpRequest, **kwargs) -> HttpResponse:
    """Public landing page for a company."""
    company = request.company
    page = CompanyPageSelector.get_for_company(company=company)
    services = CompanyServiceSelector.get_active_for_company(company=company)
    gallery = CompanyGallerySelector.get_active_for_company(company=company)

    return render(request, "tenants/home.html", {
        "company": company,
        "page": page,
        "services": services,
        "gallery": gallery,
    })


def _validate_phone(phone: str) -> str:
    """Validate Iranian phone number format. Returns error or empty string."""
    phone = phone.strip()
    if not phone:
        return "شماره تلفن الزامی است."
    if not re.match(r"^09\d{9}$", phone):
        return "شماره تلفن نامعتبر است. فرمت صحیح: 09xxxxxxxxx"
    return ""


def service_request_view(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Public service request form.
    Supports ?service=<id> for preselection.
    """
    import json
    from apps.orders.item_services import OrderItemService
    from apps.tenants.selectors import CompanyServiceCategorySelector

    company = request.company

    page = CompanyPageSelector.get_for_company(company=company)
    if not page.is_request_form_enabled:
        return render(request, "tenants/request_disabled.html", {"company": company})

    services = CompanyServiceSelector.get_active_for_company(company=company)
    error = ""
    preselected_service_id = request.GET.get("service", "")

    if request.method == "POST":
        form = ServiceRequestForm(request.POST)
        if form.is_valid():
            phone = form.cleaned_data["customer_phone"]
            phone_error = _validate_phone(phone)
            if phone_error:
                error = phone_error
            else:
                name = form.cleaned_data["customer_name"].strip()
                if not name:
                    error = "نام و نام خانوادگی الزامی است."
                else:
                    service = None
                    service_id = form.cleaned_data.get("service_id")
                    if service_id:
                        service = CompanyServiceSelector.get_by_id_for_company(
                            service_id=service_id, company=company
                        )

                    # Get optional service_category_id from POST
                    service_category_id = int(
                        request.POST.get("service_category_id") or 0
                    ) or None

                    try:
                        sr = ServiceRequestCreateService.create(
                            company=company,
                            customer_name=name,
                            customer_phone=phone,
                            customer_email=form.cleaned_data.get("customer_email", ""),
                            address=form.cleaned_data.get("address", ""),
                            service=service,
                            description=form.cleaned_data.get("description", ""),
                            preferred_time=form.cleaned_data.get("preferred_time", ""),
                            service_category_id=service_category_id,
                        )

                        # Save dynamic item values if order was created
                        if sr.order:
                            OrderItemService.save_items_from_post(
                                order=sr.order,
                                post_data=request.POST,
                                company=company,
                            )

                        # Trigger notifications
                        if sr.order:
                            NotificationEventHooks.on_order_created(order=sr.order)
                            SMSEventHooks.on_order_created(order=sr.order)

                        return render(request, "tenants/request_success.html", {
                            "company": company,
                            "service_request": sr,
                            "order": sr.order,
                        })
                    except ValueError as e:
                        error = str(e)
        else:
            error = "لطفا فیلدهای الزامی را پر کنید."
    else:
        form = ServiceRequestForm(initial={"service_id": preselected_service_id})

    # Prepare category/item data for dynamic form
    categories = CompanyServiceCategorySelector.get_active_for_company(company=company)
    item_definitions_json = json.dumps(
        OrderItemService.get_definitions_json(company=company)
    )
    return render(request, "tenants/request_form.html", {
        "company": company,
        "form": form,
        "services": services,
        "categories": categories,
        "item_definitions_json": item_definitions_json,
        "error": error,
        "preselected_service_id": preselected_service_id,
    })


def service_request_status(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Public status lookup page.
    Customer checks request status by phone number.
    """
    company = request.company
    results = None
    phone = ""

    if request.method == "POST":
        phone = request.POST.get("phone", "").strip()
        if phone:
            from apps.accounts.models import Customer
            customer = Customer.objects.filter(company=company, phone=phone).first()
            if customer:
                results = Order.objects.filter(
                    company=company, customer=customer
                ).order_by("-created_at")[:10]
            else:
                results = []

    return render(request, "tenants/request_status.html", {
        "company": company,
        "results": results,
        "phone": phone,
    })


def redirect_legacy_technician_home(request: HttpRequest, **kwargs) -> HttpResponse:
    """Redirect legacy /<company>/technician/ to the technician namespace."""
    return redirect(f"/{request.company.code}/tech/")


def redirect_legacy_notifications(request: HttpRequest, **kwargs) -> HttpResponse:
    """Route old notification URL to the role-specific namespace.

    Note: As of Phase 24, this is superseded by views_redirects.legacy_notifications_redirect
    which is wired directly in tenants/urls.py. Kept for any external callers.
    """
    from .views_redirects import legacy_notifications_redirect
    return legacy_notifications_redirect(request, **kwargs)



def redirect_customer_to_public(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Customer portal is deprecated. Redirect to company public page.
    Customer model is kept internally for order/contact data.
    """
    company = getattr(request, "company", None)
    if company:
        return redirect(f"/{company.code}/")
    return redirect("/")



def redirect_customer_admin_to_orders(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Customer management pages are deprecated.
    Redirect to orders list. Customer data is kept internally for orders.
    """
    company = getattr(request, "company", None)
    if company:
        return redirect(f"/{company.code}/admin/orders/")
    return redirect("/")
