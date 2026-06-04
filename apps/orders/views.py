"""
Orders - Views.

Thin views that delegate all business logic to services/selectors.
Access control uses decorators and permission functions.

IMPORTANT: No business logic in views. Views only:
1. Validate request
2. Call services/selectors
3. Return response
"""
from django.http import Http404, HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render

from apps.accounts.models import UserRole
from apps.accounts.permissions import require_tenant_auth, require_tenant_role

from . import permissions as order_perms
from .forms import OrderCreateForm
from .models import Order
from .selectors import OrderSelector
from .services import (
    OrderAcceptService,
    OrderCancelService,
    OrderCompleteService,
    OrderCreateService,
    TechnicianAcceptService,
)


@require_tenant_auth
def order_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    List orders based on user role.
    - Admin/Staff: all company orders
    - Technician: assigned orders + visible orders for acceptance
    - Customer: own orders only
    """
    user = request.user
    company = request.company

    if user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
        return redirect(f"/{company.code}/admin/orders/")
    elif user.role == UserRole.TECHNICIAN:
        return redirect(f"/{company.code}/tech/orders/my/")
    elif user.role == UserRole.CUSTOMER:
        customer = getattr(user, "customer_profile", None)
        if customer:
            orders = OrderSelector.get_for_customer(customer=customer)
        else:
            orders = Order.objects.none()
    else:
        orders = Order.objects.none()

    can_create_order = user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]

    return render(request, "orders/list.html", {
        "orders": orders,
        "company": company,
        "can_create_order": can_create_order,
    })


@require_tenant_auth
def order_detail(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """View a single order. Permission checked via can_view_order."""
    company = request.company
    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)

    if order is None:
        raise Http404("Order not found.")

    legacy_public_prefix = f"/{company.code}/orders/"
    if request.path.startswith(legacy_public_prefix):
        if request.user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
            return redirect(f"/{company.code}/admin/orders/{order.id}/")
        if request.user.role == UserRole.TECHNICIAN:
            return redirect(f"/{company.code}/tech/orders/{order.id}/")

    if not order_perms.can_view_order(user=request.user, order=order):
        return HttpResponseForbidden("Access denied.")

    from .item_services import OrderItemService
    from .selectors import OrderStatusLogSelector

    technician = getattr(request.user, "technician_profile", None)
    is_assigned_technician = bool(
        request.user.role == UserRole.TECHNICIAN
        and technician
        and order.technician_id == technician.id
    )

    return render(request, "orders/detail.html", {
        "order": order,
        "company": company,
        "item_values": OrderItemService.get_values_display(order=order),
        "status_logs": OrderStatusLogSelector.get_for_order(order=order)[:20],
        "is_assigned_technician": is_assigned_technician,
        "can_accept": order_perms.can_accept_order(user=request.user, order=order),
        "can_complete": order_perms.can_complete_order(user=request.user, order=order),
        "can_cancel": order_perms.can_cancel_order(user=request.user, order=order),
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def order_create(request: HttpRequest, **kwargs) -> HttpResponse:
    """Create a new order. Only admin/staff can create."""
    company = request.company
    error = ""

    if request.method == "POST":
        form = OrderCreateForm(request.POST)
        if form.is_valid():
            from apps.accounts.models import Customer
            customer = Customer.objects.filter(
                id=form.cleaned_data["customer_id"],
                company=company,
            ).first()

            if not customer:
                error = "Customer not found."
            else:
                try:
                    order = OrderCreateService.create(
                        company=company,
                        customer=customer,
                        title=form.cleaned_data["title"],
                        description=form.cleaned_data.get("description", ""),
                        address=form.cleaned_data.get("address", ""),
                        priority=form.cleaned_data["priority"],
                        price_estimate=form.cleaned_data.get("price_estimate") or 0,
                        required_skill=form.cleaned_data.get("required_skill", ""),
                        created_by=request.user,
                    )
                    return redirect(f"/{company.code}/admin/orders/{order.id}/")
                except ValueError as e:
                    error = str(e)
    else:
        form = OrderCreateForm()

    # Get customers for the company (for selection)
    from apps.accounts.models import Customer
    customers = Customer.objects.filter(company=company)

    return render(request, "orders/create.html", {
        "form": form,
        "company": company,
        "customers": customers,
        "error": error,
    })


@require_tenant_auth
def order_accept(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """Technician accepts an order."""
    company = request.company
    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)

    if order is None:
        raise Http404("Order not found.")

    if not order_perms.can_accept_order(user=request.user, order=order):
        return HttpResponseForbidden("Cannot accept this order.")

    if request.method == "POST":
        technician = getattr(request.user, "technician_profile", None)
        if not technician:
            return HttpResponseForbidden("Technician profile not found.")

        try:
            # Use new category-based accept if order has service_category
            if order.service_category_id is not None:
                TechnicianAcceptService.accept(
                    order=order,
                    technician=technician,
                    accepted_by=request.user,
                )
            else:
                # Fallback to legacy skill-based accept
                OrderAcceptService.accept(
                    order=order,
                    technician=technician,
                    accepted_by=request.user,
                )
            return redirect(f"/{company.code}/tech/orders/{order.id}/")
        except ValueError as e:
            return render(request, "orders/detail.html", {
                "order": order,
                "company": company,
                "error": str(e),
            })

    return redirect(f"/{company.code}/tech/orders/{order.id}/")


@require_tenant_auth
def order_complete(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """Mark an order as complete."""
    company = request.company
    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)

    if order is None:
        raise Http404("Order not found.")

    if not order_perms.can_complete_order(user=request.user, order=order):
        return HttpResponseForbidden("Cannot complete this order.")

    if request.method == "POST":
        final_price = request.POST.get("final_price")
        try:
            OrderCompleteService.complete(
                order=order,
                completed_by=request.user,
                final_price=int(final_price) if final_price else None,
            )
            return redirect(f"/{company.code}/tech/orders/{order.id}/")
        except ValueError as e:
            return render(request, "orders/detail.html", {
                "order": order,
                "company": company,
                "error": str(e),
            })

    return redirect(f"/{company.code}/tech/orders/{order.id}/")


@require_tenant_auth
def order_cancel(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """Cancel or request cancellation of an order."""
    company = request.company
    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)

    if order is None:
        raise Http404("Order not found.")

    if not order_perms.can_cancel_order(user=request.user, order=order):
        return HttpResponseForbidden("Cannot cancel this order.")

    if request.method == "POST":
        reason = request.POST.get("reason", "")

        try:
            # Admin/Staff can force cancel
            if request.user.role in [UserRole.COMPANY_ADMIN, UserRole.COMPANY_STAFF]:
                OrderCancelService.force_cancel(
                    order=order,
                    cancelled_by=request.user,
                    reason=reason,
                )
            else:
                # Technician/Customer can only request cancellation
                OrderCancelService.request_cancel(
                    order=order,
                    requested_by=request.user,
                    reason=reason,
                )
            return redirect(f"/{company.code}/tech/orders/{order.id}/")
        except ValueError as e:
            return render(request, "orders/detail.html", {
                "order": order,
                "company": company,
                "error": str(e),
            })

    return redirect(f"/{company.code}/tech/orders/{order.id}/")




@require_tenant_role("TECHNICIAN")
def technician_available_orders(request: HttpRequest, **kwargs) -> HttpResponse:
    from django.db.models import Q
    from apps.common.jalali import parse_jalali_date
    from .item_services import OrderItemService
    from .selectors import TechnicianOrderVisibilitySelector

    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    if not technician:
        return HttpResponseForbidden("Technician profile not found.")

    q = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    date_from_raw = (request.GET.get("from") or "").strip()
    date_to_raw = (request.GET.get("to") or "").strip()

    orders = TechnicianOrderVisibilitySelector.get_available_orders(technician=technician)

    if q:
        orders = orders.filter(
            Q(customer_name__icontains=q)
            | Q(customer_phone__icontains=q)
            | Q(address__icontains=q)
            | Q(description__icontains=q)
        )

    if status_filter:
        orders = orders.filter(status=status_filter)

    date_from = parse_jalali_date(date_from_raw)
    date_to = parse_jalali_date(date_to_raw)
    if date_from:
        orders = orders.filter(service_date__gte=date_from)
    if date_to:
        orders = orders.filter(service_date__lte=date_to)

    orders_with_items = []
    for order in orders[:50]:
        accept_allowed = order_perms.can_accept_order(user=request.user, order=order)
        # Only show orders that are currently acceptable (not future-gated)
        if not accept_allowed:
            continue
        orders_with_items.append({
            "order": order,
            "item_values": OrderItemService.get_values_display(order=order),
            "accept_allowed": accept_allowed,
            "accept_block_reason": "",
        })

    return render(request, "orders/technician_available.html", {
        "orders_with_items": orders_with_items,
        "company": company,
        "statuses": Order.Status.choices,
        "filters": {"q": q, "status": status_filter, "from": date_from_raw, "to": date_to_raw},
    })


@require_tenant_role("TECHNICIAN")
def technician_my_orders(request: HttpRequest, **kwargs) -> HttpResponse:
    from django.db.models import Q
    from apps.common.jalali import parse_jalali_date
    from .item_services import OrderItemService

    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    if not technician:
        return HttpResponseForbidden("Technician profile not found.")

    q = (request.GET.get("q") or "").strip()
    status_filter = (request.GET.get("status") or "").strip()
    date_from_raw = (request.GET.get("from") or "").strip()
    date_to_raw = (request.GET.get("to") or "").strip()

    orders_qs = Order.objects.filter(company=company, technician=technician).order_by("-created_at")

    if q:
        orders_qs = orders_qs.filter(
            Q(customer_name__icontains=q)
            | Q(customer_phone__icontains=q)
            | Q(address__icontains=q)
            | Q(description__icontains=q)
        )

    if status_filter:
        orders_qs = orders_qs.filter(status=status_filter)

    date_from = parse_jalali_date(date_from_raw)
    date_to = parse_jalali_date(date_to_raw)
    if date_from:
        orders_qs = orders_qs.filter(service_date__gte=date_from)
    if date_to:
        orders_qs = orders_qs.filter(service_date__lte=date_to)

    orders_with_items = []
    for order in orders_qs[:50]:
        orders_with_items.append({"order": order, "item_values": OrderItemService.get_values_display(order=order)})

    return render(request, "orders/technician_my_orders.html", {
        "orders_with_items": orders_with_items,
        "company": company,
        "statuses": Order.Status.choices,
        "status_filter": status_filter,
        "filters": {"q": q, "status": status_filter, "from": date_from_raw, "to": date_to_raw},
    })

@require_tenant_role("TECHNICIAN")
def technician_status_update(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """Technician updates the status of their own assigned order."""
    from .services import TechnicianStatusUpdateService

    company = request.company
    technician = getattr(request.user, "technician_profile", None)

    if not technician:
        return HttpResponseForbidden("Technician profile not found.")

    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)
    if order is None:
        raise Http404("Order not found.")

    if request.method == "POST":
        new_status = request.POST.get("new_status", "")
        note = request.POST.get("note", "")
        try:
            TechnicianStatusUpdateService.update_status(
                order=order,
                technician=technician,
                new_status=new_status,
                updated_by=request.user,
                note=note,
            )
            return redirect(f"/{company.code}/tech/orders/my/")
        except ValueError as e:
            return render(request, "orders/detail.html", {
                "order": order,
                "company": company,
                "error": str(e),
            })

    return redirect(f"/{company.code}/tech/orders/{order.id}/")

@require_tenant_role("TECHNICIAN")
def technician_invoice_create(request: HttpRequest, order_id: int, **kwargs) -> HttpResponse:
    """
    Create a draft invoice from one of the logged-in technician's assigned orders.

    If an active (non-cancelled) invoice already exists for this order,
    redirect to it instead of creating a duplicate.

    This is the quick-create action from the order detail page. It creates a
    DRAFT invoice and redirects to the technician invoice detail page.
    Access is limited to the assigned technician only.
    """
    company = request.company
    technician = getattr(request.user, "technician_profile", None)
    if technician is None:
        return HttpResponseForbidden("Technician profile not found.")

    order = OrderSelector.get_by_id_for_company(order_id=order_id, company=company)
    if order is None:
        raise Http404("سفارش یافت نشد.")

    if order.technician_id != technician.id:
        return HttpResponseForbidden("شما اجازه صدور فاکتور برای این سفارش را ندارید.")

    if request.method != "POST":
        return redirect(f"/{company.code}/tech/orders/my/")

    from apps.invoices.services import InvoiceCreateService, InvoiceItemBulkService, InvoiceDuplicateGuard
    from apps.orders.item_services import OrderItemService

    # Duplicate guard: reuse existing active invoice instead of creating another
    existing = InvoiceDuplicateGuard.get_active_for_order(company=company, order=order)
    if existing is not None:
        return redirect(f"/{company.code}/tech/invoices/{existing.id}/")

    invoice = InvoiceCreateService.create_from_order(order=order, created_by=request.user)

    # Best-effort: create initial invoice rows from the order's dynamic item values.
    # Money items become invoice rows with amount. Non-money items are shown with zero price
    # so the technician/customer can still see what was ordered.
    invoice_items = []
    for entry in OrderItemService.get_values_display(order=order):
        definition = entry.get("definition")
        value = entry.get("value")
        if not definition:
            continue

        description = str(getattr(definition, "title", "")).strip()
        if not description:
            continue

        unit_price = 0
        quantity = 1
        try:
            kind = getattr(definition, "kind", "")
            if kind == "money" and value not in (None, ""):
                unit_price = int(float(value))
            elif kind == "number" and value not in (None, ""):
                quantity = max(1, int(float(value)))
            elif kind == "bool":
                description = f"{description}: {'بله' if value else 'خیر'}"
            elif value not in (None, ""):
                description = f"{description}: {value}"
        except Exception:
            pass

        invoice_items.append({
            "description": description,
            "quantity": quantity,
            "unit_price": unit_price,
            "discount_amount": 0,
        })

    if invoice_items:
        InvoiceItemBulkService.replace_items(invoice=invoice, items=invoice_items)
        invoice.recalculate_totals(save=True)

    return redirect(f"/{company.code}/tech/invoices/{invoice.id}/")

