"""
Invoices - Technician Views.

Views for technician invoice management:
- technician_invoice_list: list invoices for the logged-in technician
- technician_invoice_create: create an invoice from a technician's assigned order
- technician_invoice_detail: view invoice detail with SMS link support
"""
from decimal import Decimal, InvalidOperation
from urllib.parse import quote as _url_quote

from django.conf import settings as _django_settings
from django.contrib import messages
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.models import Technician
from apps.accounts.permissions import require_tenant_role
from apps.invoices.models import Invoice
from apps.orders.models import Order


# =============================================================================
# SHARED HELPERS
# =============================================================================


def _company(request):
    return getattr(request, "company", None)


def _technician(request, company):
    return get_object_or_404(Technician, user=request.user, company=company)


def _safe_get(obj, *names, default=""):
    for name in names:
        value = getattr(obj, name, None)
        if value not in (None, ""):
            return value
    return default


def _to_decimal(value, default="0"):
    try:
        if value is None or value == "":
            return Decimal(default)
        return Decimal(str(value).replace(",", "").strip())
    except (InvalidOperation, ValueError, TypeError):
        return Decimal(default)


def _item_title(obj):
    for attr in ("title", "name", "description"):
        value = getattr(obj, attr, None)
        if value:
            return str(value)
    return str(obj)


def _item_price(obj):
    for attr in ("price", "base_price", "unit_price", "amount", "total_price"):
        value = getattr(obj, attr, None)
        if value is not None:
            return _to_decimal(value)
    return Decimal("0")


def _order_initial_items(order):
    rows = []
    related_values = []

    for rel_name in ("item_values", "items", "order_items"):
        try:
            rel = getattr(order, rel_name)
            related_values = list(rel.all())
            if related_values:
                break
        except Exception:
            continue

    for value in related_values:
        item = getattr(value, "item", None) or getattr(value, "service_item", None) or value
        title = _item_title(item)

        qty = (
            getattr(value, "quantity", None)
            or getattr(value, "qty", None)
            or getattr(value, "count", None)
            or 1
        )
        qty = _to_decimal(qty, "1")
        if qty <= 0:
            qty = Decimal("1")

        price = _item_price(value) or _item_price(item)
        if price < 0:
            price = Decimal("0")

        rows.append({
            "row_type": "service",
            "description": title,
            "quantity": qty,
            "unit_price": price,
            "discount_amount": Decimal("0"),
        })

    if not rows:
        rows.append({
            "row_type": "service",
            "description": _safe_get(order, "title", default="خدمت سفارش"),
            "quantity": Decimal("1"),
            "unit_price": _to_decimal(_safe_get(order, "price_estimate", "estimated_price", default="0")),
            "discount_amount": Decimal("0"),
        })

    return rows


def _snapshot(order, technician):
    user = getattr(technician, "user", None)

    technician_name = ""
    technician_phone = ""

    if user:
        get_full_name = getattr(user, "get_full_name", None)
        technician_name = (
            _safe_get(user, "full_name")
            or (get_full_name() if callable(get_full_name) else "")
            or _safe_get(user, "username")
        )
        technician_phone = _safe_get(user, "phone", "mobile")

    return {
        "customer_name_snapshot": _safe_get(order, "customer_name", "display_customer_name"),
        "customer_phone_snapshot": _safe_get(order, "customer_phone", "display_customer_phone"),
        "address_snapshot": _safe_get(order, "address_text", "address", "display_address"),
        "technician_name_snapshot": technician_name,
        "technician_phone_snapshot": technician_phone,
        "service_title_snapshot": (
            _safe_get(getattr(order, "service_category", None), "title")
            or _safe_get(getattr(order, "category", None), "title")
            or _safe_get(order, "title", default="خدمت")
        ),
        "service_date_snapshot": _safe_get(order, "service_date", default=None),
    }


def _choices_for(model, field_name):
    try:
        return model._meta.get_field(field_name).choices
    except Exception:
        return []


def _person_name(user):
    """Get display name for a user object."""
    if not user:
        return ""
    full_name_attr = getattr(user, "full_name", "")
    if full_name_attr:
        return full_name_attr
    get_full_name = getattr(user, "get_full_name", None)
    if callable(get_full_name):
        full_name = get_full_name()
        if full_name:
            return full_name
    return getattr(user, "username", "") or ""


def _person_phone(user):
    """Get phone number for a user object."""
    if not user:
        return ""
    return getattr(user, "phone", "") or getattr(user, "mobile", "") or ""


def _company_name(company):
    """Get display name for a company."""
    return (
        getattr(company, "name", "")
        or getattr(company, "title", "")
        or getattr(company, "display_name", "")
        or "شرکت"
    )


def _company_invoice_terms(company):
    """Get invoice terms/footer text for a company."""
    for name in [
        "invoice_terms",
        "invoice_terms_text",
        "invoice_footer_text",
        "invoice_footer_note",
        "invoice_default_note",
        "invoice_note",
        "terms_and_conditions",
        "terms_text",
        "footer_text",
    ]:
        value = getattr(company, name, None)
        if value:
            return value
    return "مسئولیت بررسی اقلام، مبالغ و تأیید نهایی فاکتور بر عهده شرکت ارائه‌دهنده خدمات است."


def _ensure_public_code(invoice):
    """Get or generate the canonical public_code for an invoice."""
    code = getattr(invoice, "public_code", "") or ""
    if code:
        return code

    if hasattr(invoice, "ensure_public_code"):
        invoice.ensure_public_code()
        try:
            invoice.save(update_fields=["public_code"])
        except Exception:
            invoice.save()
        return invoice.public_code

    return str(invoice.id)


def _public_invoice_url(invoice):
    """Build the public invoice URL for SMS sharing."""
    base_url = (
        getattr(_django_settings, "PUBLIC_SITE_URL", "")
        or getattr(_django_settings, "SITE_URL", "")
        or getattr(_django_settings, "FRONTEND_URL", "")
        or ("http://127.0.0.1:8002" if getattr(_django_settings, "DEBUG", False) else "https://site.ir")
    ).rstrip("/")

    return f"{base_url}/i/{_ensure_public_code(invoice)}/"


def _sms_href_and_body(company, invoice, request=None):
    """
    Build sms: href link, SMS body text, and public invoice URL.

    This manual phone SMS link is independent from platform/admin SMS settings.
    It is only used by the technician's own phone SMS app.
    """
    phone = (
        getattr(invoice, "customer_phone_snapshot", "")
        or getattr(getattr(invoice, "order", None), "customer_phone", "")
        or ""
    )

    code = _ensure_public_code(invoice)
    if request is not None:
        scheme = "https" if request.is_secure() else "http"
        public_url = f"{scheme}://{request.get_host()}/i/{code}/"
    else:
        public_url = _public_invoice_url(invoice)

    body = f"فاکتور {_company_name(company)}:\n{public_url}"

    # sms: is handled by the user's mobile OS.
    return f"sms:{phone}?body={_url_quote(body)}", body, public_url


# =============================================================================
# VIEWS
# =============================================================================


@require_tenant_role("TECHNICIAN")
def technician_invoice_list(request, company_code=None, **kwargs):
    company = _company(request)
    technician = _technician(request, company)

    invoices = (
        Invoice.objects
        .filter(company=company, order__technician=technician)
        .select_related("order", "company")
        .prefetch_related("items")
        .order_by("-created_at")
    )

    q = (request.GET.get("q") or "").strip()
    status = (request.GET.get("status") or "").strip()
    order_id = (request.GET.get("order") or "").strip()
    date_from = (request.GET.get("from") or "").strip()
    date_to = (request.GET.get("to") or "").strip()

    if q:
        invoices = invoices.filter(
            Q(customer_name_snapshot__icontains=q)
            | Q(customer_phone_snapshot__icontains=q)
            | Q(address_snapshot__icontains=q)
            | Q(order__customer_name__icontains=q)
            | Q(order__customer_phone__icontains=q)
            | Q(order__address_text__icontains=q)
        )

    if status:
        invoices = invoices.filter(status=status)

    if order_id.isdigit():
        invoices = invoices.filter(order_id=int(order_id))

    if date_from:
        invoices = invoices.filter(created_at__date__gte=date_from)

    if date_to:
        invoices = invoices.filter(created_at__date__lte=date_to)

    invoice_list = list(invoices)

    total_amount = Decimal("0")
    service_total = Decimal("0")
    travel_total = Decimal("0")
    goods_total = Decimal("0")

    for invoice in invoice_list:
        total_amount += _to_decimal(getattr(invoice, "total_amount", 0))
        for item in invoice.items.all():
            amount = _to_decimal(getattr(item, "total_price", 0))
            description = getattr(item, "description", "") or ""
            if "ایاب" in description or "ذهاب" in description:
                travel_total += amount
            else:
                service_total += amount

    return render(request, "orders/technician_invoices.html", {
        "company": company,
        "invoices": invoice_list,
        "current_q": q,
        "current_status": status,
        "current_order": order_id,
        "from": date_from,
        "to": date_to,
        "status_choices": _choices_for(Invoice, "status"),
        "summary": {
            "count": len(invoice_list),
            "total_amount": total_amount,
            "service_total": service_total,
            "goods_total": goods_total,
            "travel_total": travel_total,
        },
    })


@require_tenant_role("TECHNICIAN")
def technician_invoice_create(request, order_id, company_code=None, **kwargs):
    company = _company(request)
    technician = _technician(request, company)

    order = get_object_or_404(
        Order.objects.select_related("company", "technician"),
        id=order_id,
        company=company,
        technician=technician,
    )

    # Duplicate guard: if an active (non-cancelled) invoice already exists for
    # this order, redirect to it instead of creating a new one.
    from apps.invoices.services import InvoiceDuplicateGuard, InvoiceCreateService, InvoiceItemBulkService, InvoiceIssueService

    existing_invoice = InvoiceDuplicateGuard.get_active_for_order(
        company=company, order=order
    )
    if existing_invoice is not None:
        # If already issued/paid, just redirect to detail
        if existing_invoice.status in (Invoice.Status.ISSUED, Invoice.Status.PAID):
            messages.info(request, "فاکتور این سفارش قبلاً صادر شده است.")
            return redirect(f"/{company.code}/tech/invoices/{existing_invoice.id}/")
        # If draft, allow the technician to fill in the form (will update this draft)
        # Fall through to show form with existing draft as target
        pass

    initial_items = _order_initial_items(order)

    if request.method != "POST":
        return render(request, "orders/technician_invoice_create.html", {
            "company": company,
            "order": order,
            "initial_items": initial_items,
        })

    row_types = request.POST.getlist("row_type")
    descriptions = request.POST.getlist("description")
    quantities = request.POST.getlist("quantity")
    unit_prices = request.POST.getlist("unit_price")
    discounts = request.POST.getlist("discount_amount")

    travel_quantity = _to_decimal(request.POST.get("travel_quantity"), "0")
    travel_unit_price = _to_decimal(request.POST.get("travel_fee"), "0")
    extra_discount = _to_decimal(request.POST.get("extra_discount"), "0")
    notes = (request.POST.get("notes") or "").strip()

    if travel_quantity < 0:
        travel_quantity = Decimal("0")
    if travel_unit_price < 0:
        travel_unit_price = Decimal("0")
    if extra_discount < 0:
        extra_discount = Decimal("0")

    item_rows = []
    row_discount_total = Decimal("0")

    for idx, desc in enumerate(descriptions):
        desc = (desc or "").strip()
        if not desc:
            continue

        row_type = row_types[idx] if idx < len(row_types) else "service"
        if row_type not in ("service", "product"):
            row_type = "service"

        qty = _to_decimal(quantities[idx] if idx < len(quantities) else "0", "0")
        unit = _to_decimal(unit_prices[idx] if idx < len(unit_prices) else "0", "0")
        discount = _to_decimal(discounts[idx] if idx < len(discounts) else "0", "0")

        if qty <= 0:
            qty = Decimal("1")
        if unit < 0:
            unit = Decimal("0")
        if discount < 0:
            discount = Decimal("0")

        row_total = (qty * unit) - discount
        if row_total < 0:
            row_total = Decimal("0")

        row_discount_total += discount

        item_rows.append({
            "row_type": row_type,
            "description": desc,
            "quantity": qty,
            "unit_price": unit,
            "discount_amount": discount,
            "total_price": row_total,
        })

    travel_total = travel_quantity * travel_unit_price
    if travel_quantity > 0 and travel_unit_price > 0:
        item_rows.append({
            "row_type": "travel",
            "description": "ایاب و ذهاب",
            "quantity": travel_quantity,
            "unit_price": travel_unit_price,
            "discount_amount": Decimal("0"),
            "total_price": travel_total,
        })

    if not item_rows:
        messages.error(request, "برای صدور فاکتور حداقل یک ردیف لازم است.")
        return render(request, "orders/technician_invoice_create.html", {
            "company": company,
            "order": order,
            "initial_items": initial_items,
        })

    # Build items list for service layer (include row_type for wage calculation)
    service_items = []
    for row in item_rows:
        # Map form row_type to InvoiceItem.RowType
        form_row_type = row.get("row_type", "service")
        if form_row_type == "product":
            form_row_type = "goods"
        elif form_row_type not in ("service", "goods", "travel"):
            form_row_type = "service"
        service_items.append({
            "description": row["description"],
            "quantity": row["quantity"],
            "unit_price": row["unit_price"],
            "discount_amount": row["discount_amount"],
            "row_type": form_row_type,
        })

    # Extra/manual discount is invoice-level financial data.
    # It must NOT be saved as an InvoiceItem row, otherwise it is mixed into
    # row_discount_amount and technician/category totals.
    total_discount = extra_discount

    with transaction.atomic():
        # Re-check duplicate inside transaction to avoid race condition
        existing_invoice = InvoiceDuplicateGuard.get_active_for_order(
            company=company, order=order
        )

        if existing_invoice is not None and existing_invoice.status == Invoice.Status.DRAFT:
            # Reuse the existing draft: replace its items and issue it
            invoice = existing_invoice
            InvoiceItemBulkService.replace_items(invoice=invoice, items=service_items)
            invoice.extra_discount_amount = extra_discount
            invoice.notes = notes
            invoice.save(update_fields=["extra_discount_amount", "notes", "updated_at"])
            invoice.recalculate_totals(save=True)
        elif existing_invoice is not None:
            # Already issued/paid — cannot create another
            messages.info(request, "فاکتور این سفارش قبلاً صادر شده است.")
            return redirect(f"/{company.code}/tech/invoices/{existing_invoice.id}/")
        else:
            # Create new invoice via service layer
            snapshots = _snapshot(order, technician)
            invoice = InvoiceCreateService.create(
                company=company,
                customer=getattr(order, "customer", None),
                order=order,
                created_by=request.user,
                items=service_items,
                notes=notes,
                discount_amount=extra_discount,
                **snapshots,
            )

        # Issue the invoice (DRAFT → ISSUED)
        if invoice.status == Invoice.Status.DRAFT:
            try:
                InvoiceIssueService.issue(invoice=invoice)
            except ValueError:
                # If issue fails (e.g., zero amount), keep as draft and show to technician
                messages.warning(request, "فاکتور ساخته شد ولی مبلغ صفر است. لطفاً ردیف‌ها را بررسی کنید.")
                return redirect(f"/{company.code}/tech/invoices/{invoice.id}/")

    messages.success(request, f"فاکتور #{invoice.id} با موفقیت صادر شد.")
    _emit_invoice_issued_customer_event(invoice, getattr(request, "user", None))
    return redirect(f"/{company.code}/tech/invoices/{invoice.id}/")


# Backward-compatible alias
technician_invoice_create_from_order = technician_invoice_create


@require_tenant_role("TECHNICIAN")
def technician_invoice_detail(request, invoice_id, company_code=None, **kwargs):
    """
    Technician invoice detail view with manual SMS link support.

    Context variables provided to template:
    - company, invoice, invoice_items, invoice_summary
    - company_invoice_terms, technician_name, technician_phone
    - sms_href, sms_body, public_invoice_url
    """
    company = getattr(request, "company", None)
    technician = get_object_or_404(
        Technician,
        user=request.user,
        company=company,
    )

    invoice = get_object_or_404(
        Invoice.objects.select_related("order", "company").prefetch_related("items"),
        id=invoice_id,
        company=company,
        order__technician=technician,
    )

    all_items = list(invoice.items.all().order_by("sort_order", "id"))

    # Legacy safety: old invoices may contain an InvoiceItem named "تخفیف مازاد".
    # Hide that row from the item table and treat it as invoice-level extra discount
    # for display only. New invoices must store this in Invoice.extra_discount_amount.
    invoice_items = []
    legacy_extra_discount_total = Decimal("0")
    for item in all_items:
        description = (getattr(item, "description", "") or "").strip()
        if description == "تخفیف مازاد":
            legacy_extra_discount_total += _to_decimal(getattr(item, "discount_amount", 0))
            continue
        invoice_items.append(item)

    rows_gross_total = _to_decimal(getattr(invoice, "gross_amount", 0))
    row_discount_total = _to_decimal(getattr(invoice, "row_discount_amount", 0))
    net_amount_before_invoice_discounts = _to_decimal(getattr(invoice, "net_amount_before_invoice_discounts", 0))
    extra_discount_total = _to_decimal(getattr(invoice, "extra_discount_amount", 0))
    if extra_discount_total <= 0 and legacy_extra_discount_total > 0:
        extra_discount_total = legacy_extra_discount_total
    campaign_discount_total = _to_decimal(getattr(invoice, "campaign_discount_amount", 0))
    total_invoice_discount = extra_discount_total + campaign_discount_total
    payable_amount = _to_decimal(getattr(invoice, "total_amount", 0))

    technician_name = (
        getattr(invoice, "technician_name_snapshot", "")
        or _person_name(getattr(technician, "user", None))
    )
    technician_phone = (
        getattr(invoice, "technician_phone_snapshot", "")
        or _person_phone(getattr(technician, "user", None))
    )

    sms_href, sms_body, public_invoice_url = _sms_href_and_body(company, invoice, request=request)
    latest_payment = invoice.payments.order_by("-created_at").first()

    return render(request, "orders/technician_invoice_detail.html", {
        "company": company,
        "invoice": invoice,
        "invoice_items": invoice_items,
        "invoice_summary": {
            "rows_gross_total": rows_gross_total,
            "row_discount_total": row_discount_total,
            "net_amount_before_invoice_discounts": net_amount_before_invoice_discounts,
            "extra_discount_total": extra_discount_total,
            "campaign_discount_total": campaign_discount_total,
            "total_invoice_discount": total_invoice_discount,
            "payable_amount": payable_amount,
        },
        "company_invoice_terms": _company_invoice_terms(company),
        "technician_name": technician_name,
        "technician_phone": technician_phone,

        # Manual SMS by technician phone only:
        "sms_href": sms_href,
        "sms_body": sms_body,
        "public_invoice_url": public_invoice_url,
        "latest_payment": latest_payment,
    })


# =============================================================================
# EVENT HOOK
# =============================================================================


def _emit_invoice_issued_customer_event(invoice, actor=None):
    """
    Central notification hook for technician invoice creation.

    This helper must NOT have any Django view decorator.
    Business apps should not import SMS directly.
    """
    if invoice is None or not getattr(invoice, "id", None):
        return None

    try:
        from apps.notifications.services_events import NotificationEventService
        return NotificationEventService.emit(
            event_key="invoice_issued_customer",
            company=getattr(invoice, "company", None),
            actor=actor,
            target=invoice,
        )
    except Exception:
        # Never break invoice creation because of a notification issue.
        return None

@require_tenant_role("TECHNICIAN")
def technician_invoice_mark_cash_paid(request, invoice_id, company_code=None, **kwargs):
    from apps.invoices.services import InvoiceMarkPaidService
    from apps.payments.models import Payment

    company = _company(request)
    technician = _technician(request, company)

    invoice = get_object_or_404(
        Invoice.objects.select_related("order", "company"),
        id=invoice_id,
        company=company,
        order__technician=technician,
    )

    if request.method != "POST":
        messages.error(request, "ثبت دریافت نقدی فقط با درخواست معتبر انجام می‌شود.")
        return redirect(f"/{company.code}/tech/invoices/{invoice.id}/")

    if invoice.status != Invoice.Status.ISSUED:
        messages.error(request, "فقط فاکتور صادرشده و پرداخت‌نشده قابل ثبت دریافت نقدی است.")
        return redirect(f"/{company.code}/tech/invoices/{invoice.id}/")

    cash_ref = f"CASH-{company.code.upper()}-{invoice.id:05d}-{timezone.now().strftime('%Y%m%d%H%M%S')}"

    with transaction.atomic():
        # Re-fetch with a row lock to prevent duplicate Payment records on double-click.
        invoice = (
            Invoice.objects
            .select_for_update()
            .get(pk=invoice.pk, company=company)
        )
        if invoice.status != Invoice.Status.ISSUED:
            messages.error(request, "فقط فاکتور صادرشده و پرداخت‌نشده قابل ثبت دریافت نقدی است.")
            return redirect(f"/{company.code}/tech/invoices/{invoice.id}/")

        # TODO: When a real gateway is added, discount finalization should move to a
        # PENDING/RESERVED design so codes are not burned until payment is confirmed.
        # For now, invoice.total_amount already reflects any applied discount.
        cash_payment = Payment.objects.create(
            company=company,
            invoice=invoice,
            gateway=None,
            amount=invoice.total_amount,
            status=Payment.Status.PAID,
            reference_id=cash_ref,
            tracking_code=cash_ref,
            paid_at=timezone.now(),
            metadata={
                "method": "cash",
                "received_by_user_id": getattr(request.user, "id", None),
                "received_by_username": getattr(request.user, "username", ""),
                "technician_id": getattr(technician, "id", None),
                "invoice_number": invoice.invoice_number,
            },
        )
        discount_code_id = None
        try:
            from apps.reports.models import DiscountCode
            code = (
                DiscountCode.objects
                .filter(company=company, used_invoice_id=invoice.id)
                .order_by("-used_at", "-id")
                .first()
            )
            discount_code_id = code.id if code else None
        except Exception:
            discount_code_id = None

        InvoiceMarkPaidService.mark_paid(
            invoice=invoice,
            payment=cash_payment,
            payment_method="cash",
            payment_reference=cash_ref,
            discount_code_id=discount_code_id,
        )

        # Cancel any unfinished online payment records for this invoice so they do
        # not appear as active in reports. Filters by company + invoice for tenant
        # safety. Never touches PAID, FAILED, or already CANCELLED payments.
        abandoned = Payment.objects.filter(
            company=company,
            invoice=invoice,
            status__in=[Payment.Status.INITIATED, Payment.Status.PENDING],
        ).exclude(pk=cash_payment.pk)
        for p in abandoned:
            p.status = Payment.Status.CANCELLED
            p.metadata = {
                **(p.metadata or {}),
                "superseded_by_cash_payment": True,
                "superseded_by_payment_id": cash_payment.pk,
                "superseded_reason": "cash_payment_confirmed",
            }
            p.save(update_fields=["status", "metadata", "updated_at"])

    messages.success(request, f"دریافت نقدی ثبت شد. شماره سند: {cash_ref}")
    return redirect(f"/{company.code}/tech/invoices/{invoice.id}/")
