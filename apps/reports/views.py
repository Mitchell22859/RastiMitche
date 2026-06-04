"""
Reports - Views.

Company-level reports for admin/staff.
All query logic is in selectors.
"""
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from apps.accounts.permissions import require_tenant_role

from .selectors import CompanyReportSelector


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def report_list(request: HttpRequest, **kwargs) -> HttpResponse:
    """Company reports overview."""
    company = request.company

    order_summary = CompanyReportSelector.order_summary(company=company)
    revenue_summary = CompanyReportSelector.revenue_summary(company=company)
    invoice_summary = CompanyReportSelector.invoice_summary(company=company)
    technician_perf = CompanyReportSelector.technician_performance(company=company)
    request_summary = CompanyReportSelector.service_request_summary(company=company)

    return render(request, "reports/list.html", {
        "company": company,
        "order_summary": order_summary,
        "revenue_summary": revenue_summary,
        "invoice_summary": invoice_summary,
        "technician_performance": technician_perf,
        "request_summary": request_summary,
    })

# =============================================================================
# CUSTOMER SEGMENT REPORT
# =============================================================================

def _segment_parse_date(value):
    value = (value or "").strip()
    if not value:
        return None

    try:
        from apps.common.jalali import normalize_digits, parse_jalali_date
        parsed = parse_jalali_date(normalize_digits(value))
        if parsed:
            return parsed
    except Exception:
        pass

    try:
        import datetime
        value = value.replace("-", "/")
        return datetime.datetime.strptime(value, "%Y/%m/%d").date()
    except Exception:
        return None


def _segment_decimal(value):
    value = (value or "").strip()
    if not value:
        return None

    try:
        from decimal import Decimal
        from apps.common.jalali import normalize_digits
        value = normalize_digits(value)
        value = value.replace(",", "").replace("٬", "").replace(" ", "")
        return Decimal(value)
    except Exception:
        return None


def _segment_int(value):
    value = (value or "").strip()
    if not value:
        return None

    try:
        from apps.common.jalali import normalize_digits
        value = normalize_digits(value)
        value = value.replace(",", "").replace("٬", "").replace(" ", "")
        return int(value)
    except Exception:
        return None


def _segment_customer_name(customer):
    name = f"{getattr(customer, 'first_name', '')} {getattr(customer, 'last_name', '')}".strip()
    return name or getattr(customer, "phone", "") or "-"


def _segment_invoice_queryset(company, customer):
    from django.db.models import Q
    from apps.invoices.models import Invoice

    phone = getattr(customer, "phone", "") or ""
    field_names = {field.name for field in Invoice._meta.fields}

    query = Q()
    has_condition = False

    if "customer" in field_names:
        query |= Q(customer=customer)
        has_condition = True

    for phone_field in ("customer_phone_snapshot", "customer_phone", "display_customer_phone", "phone_number"):
        if phone and phone_field in field_names:
            query |= Q(**{phone_field: phone})
            has_condition = True

    if not has_condition:
        return Invoice.objects.none()

    return Invoice.objects.filter(company=company).filter(query).distinct()


def _segment_order_queryset(company, customer):
    from django.db.models import Q
    from apps.orders.models import Order

    phone = getattr(customer, "phone", "") or ""
    return (
        Order.objects
        .filter(company=company)
        .filter(Q(customer=customer) | Q(customer_phone=phone))
        .distinct()
    )


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def customer_segment_report(request: HttpRequest, **kwargs) -> HttpResponse:
    import csv
    from django.db.models import Q, Sum
    from apps.accounts.models import Customer
    from apps.orders.models import Order
    from apps.invoices.models import Invoice
    from apps.tenants.models import CompanyServiceCategory

    company = request.company

    filters = {
        "name": (request.GET.get("name") or "").strip(),
        "phone": (request.GET.get("phone") or "").strip(),
        "address": (request.GET.get("address") or "").strip(),
        "invoice_from": (request.GET.get("invoice_from") or "").strip(),
        "invoice_to": (request.GET.get("invoice_to") or "").strip(),
        "invoice_amount_min": (request.GET.get("invoice_amount_min") or "").strip(),
        "invoice_amount_max": (request.GET.get("invoice_amount_max") or "").strip(),
        "invoice_status": (request.GET.get("invoice_status") or "").strip(),
        "order_from": (request.GET.get("order_from") or "").strip(),
        "order_to": (request.GET.get("order_to") or "").strip(),
        "order_count_min": (request.GET.get("order_count_min") or "").strip(),
        "order_count_max": (request.GET.get("order_count_max") or "").strip(),
        "service_category": (request.GET.get("service_category") or "").strip(),
        "order_status": (request.GET.get("order_status") or "").strip(),
    }

    invoice_from = _segment_parse_date(filters["invoice_from"])
    invoice_to = _segment_parse_date(filters["invoice_to"])
    invoice_amount_min = _segment_decimal(filters["invoice_amount_min"])
    invoice_amount_max = _segment_decimal(filters["invoice_amount_max"])

    order_from = _segment_parse_date(filters["order_from"])
    order_to = _segment_parse_date(filters["order_to"])
    order_count_min = _segment_int(filters["order_count_min"])
    order_count_max = _segment_int(filters["order_count_max"])

    customers = Customer.objects.filter(company=company)

    if filters["name"]:
        name = filters["name"]
        customers = customers.filter(Q(first_name__icontains=name) | Q(last_name__icontains=name))

    if filters["phone"]:
        customers = customers.filter(phone__icontains=filters["phone"])

    if filters["address"]:
        address = filters["address"]
        customers = customers.filter(Q(address__icontains=address) | Q(orders__address__icontains=address)).distinct()

    has_invoice_filter = any([
        invoice_from,
        invoice_to,
        invoice_amount_min is not None,
        invoice_amount_max is not None,
        filters["invoice_status"],
    ])
    has_order_filter = any([
        order_from,
        order_to,
        order_count_min is not None,
        order_count_max is not None,
        filters["service_category"],
        filters["order_status"],
    ])

    results = []
    total_order_matches = 0
    total_invoice_matches = 0
    total_invoice_amount = 0

    for customer in customers.order_by("first_name", "last_name", "phone"):
        order_qs = _segment_order_queryset(company=company, customer=customer)
        invoice_qs = _segment_invoice_queryset(company=company, customer=customer)

        if order_from:
            order_qs = order_qs.filter(created_at__date__gte=order_from)
        if order_to:
            order_qs = order_qs.filter(created_at__date__lte=order_to)
        if filters["order_status"]:
            order_qs = order_qs.filter(status=filters["order_status"])
        if filters["service_category"]:
            try:
                order_qs = order_qs.filter(service_category_id=int(filters["service_category"]))
            except (TypeError, ValueError):
                order_qs = order_qs.none()

        if invoice_from:
            invoice_qs = invoice_qs.filter(created_at__date__gte=invoice_from)
        if invoice_to:
            invoice_qs = invoice_qs.filter(created_at__date__lte=invoice_to)
        if filters["invoice_status"]:
            invoice_qs = invoice_qs.filter(status=filters["invoice_status"])
        if invoice_amount_min is not None:
            invoice_qs = invoice_qs.filter(total_amount__gte=invoice_amount_min)
        if invoice_amount_max is not None:
            invoice_qs = invoice_qs.filter(total_amount__lte=invoice_amount_max)

        order_count = order_qs.count()
        invoice_count = invoice_qs.count()

        if has_order_filter and order_count == 0:
            continue
        if order_count_min is not None and order_count < order_count_min:
            continue
        if order_count_max is not None and order_count > order_count_max:
            continue
        if has_invoice_filter and invoice_count == 0:
            continue

        invoice_sum = invoice_qs.aggregate(total=Sum("total_amount")).get("total") or 0
        last_order = order_qs.order_by("-created_at").first()
        if not last_order:
            last_order = _segment_order_queryset(company=company, customer=customer).order_by("-created_at").first()

        last_address = ""
        if last_order and getattr(last_order, "address", ""):
            last_address = last_order.address
        elif getattr(customer, "address", ""):
            last_address = customer.address

        row = {
            "customer_id": customer.id,
            "name": _segment_customer_name(customer),
            "phone": customer.phone,
            "email": customer.email,
            "order_count": order_count,
            "invoice_count": invoice_count,
            "invoice_sum": invoice_sum,
            "last_order_at": getattr(last_order, "created_at", None),
            "last_address": last_address,
        }
        results.append(row)

        total_order_matches += order_count
        total_invoice_matches += invoice_count
        total_invoice_amount += int(invoice_sum or 0)

    if request.GET.get("export") == "csv":
        response = HttpResponse(content_type="text/csv; charset=utf-8-sig")
        response["Content-Disposition"] = f'attachment; filename="customer_segment_{company.code}.csv"'
        response.write("\ufeff")
        writer = csv.writer(response)
        writer.writerow([
            "نام مشتری",
            "شماره موبایل",
            "ایمیل",
            "تعداد سفارش مطابق فیلتر",
            "تعداد فاکتور مطابق فیلتر",
            "مجموع مبلغ فاکتور",
            "آخرین آدرس",
            "لینک پرونده",
        ])
        for row in results:
            writer.writerow([
                row["name"],
                row["phone"],
                row["email"],
                row["order_count"],
                row["invoice_count"],
                row["invoice_sum"],
                row["last_address"],
                f"/{company.code}/admin/customers/{row['customer_id']}/",
            ])
        return response

    stats = {
        "total_customers": len(results),
        "total_order_matches": total_order_matches,
        "total_invoice_matches": total_invoice_matches,
        "total_invoice_amount": total_invoice_amount,
    }

    service_categories = CompanyServiceCategory.objects.filter(company=company, is_active=True).order_by("sort_order", "title")

    return render(request, "reports/customer_segments.html", {
        "company": company,
        "filters": filters,
        "results": results,
        "stats": stats,
        "service_categories": service_categories,
        "order_statuses": Order.Status.choices,
        "invoice_statuses": Invoice.Status.choices,
    })

# =============================================================================
# DISCOUNT CAMPAIGNS
# =============================================================================

def _discount_parse_expiry(value):
    from django.utils import timezone
    import datetime

    value = (value or "").strip()
    date_value = None

    if not value:
        return timezone.now() + datetime.timedelta(days=30)

    try:
        date_value = _segment_parse_date(value)
    except Exception:
        date_value = None

    if date_value is None:
        try:
            date_value = datetime.datetime.strptime(value.replace("-", "/"), "%Y/%m/%d").date()
        except Exception:
            date_value = timezone.localdate() + datetime.timedelta(days=30)

    naive = datetime.datetime.combine(date_value, datetime.time(23, 59, 59))
    return timezone.make_aware(naive, timezone.get_current_timezone())


def _discount_decimal(value, default="20"):
    try:
        from decimal import Decimal
        from apps.common.jalali import normalize_digits
        value = normalize_digits(str(value or default)).replace(",", "").replace("٬", "").strip()
        return Decimal(value)
    except Exception:
        from decimal import Decimal
        return Decimal(default)


def _discount_int(value, default=300000):
    try:
        from apps.common.jalali import normalize_digits
        value = normalize_digits(str(value or default)).replace(",", "").replace("٬", "").strip()
        return int(value)
    except Exception:
        return int(default)


def _discount_required_post_errors(request):
    """Server-side validation for campaign forms; placeholders are examples, not submitted values."""
    errors = []
    labels = {
        "title": "عنوان کمپین",
        "percent": "درصد تخفیف",
        "max_discount_rial": "سقف تخفیف ریال",
        "expires_at": "تاریخ انقضا",
    }

    for field, label in labels.items():
        if not (request.POST.get(field) or "").strip():
            errors.append(f"{label} الزامی است.")

    if (request.POST.get("percent") or "").strip():
        percent = _discount_decimal(request.POST.get("percent"), "0")
        if percent <= 0 or percent > 100:
            errors.append("درصد تخفیف باید بین 1 تا 100 باشد.")

    if (request.POST.get("max_discount_rial") or "").strip():
        max_discount = _discount_int(request.POST.get("max_discount_rial"), 0)
        if max_discount <= 0:
            errors.append("سقف تخفیف باید بیشتر از صفر باشد.")

    if (request.POST.get("expires_at") or "").strip():
        try:
            expires = _discount_parse_expiry(request.POST.get("expires_at"))
            from django.utils import timezone
            if expires <= timezone.now():
                errors.append("تاریخ انقضا باید بعد از امروز باشد.")
        except Exception:
            errors.append("تاریخ انقضا معتبر نیست.")

    return errors


def _discount_segment_candidates(request, company):
    """Reuse the same filtering logic as the customer segment report."""
    from django.db.models import Q, Sum
    from apps.accounts.models import Customer
    from apps.orders.models import Order

    filters = {
        "name": (request.GET.get("name") or "").strip(),
        "phone": (request.GET.get("phone") or "").strip(),
        "address": (request.GET.get("address") or "").strip(),
        "invoice_from": (request.GET.get("invoice_from") or "").strip(),
        "invoice_to": (request.GET.get("invoice_to") or "").strip(),
        "invoice_amount_min": (request.GET.get("invoice_amount_min") or "").strip(),
        "invoice_amount_max": (request.GET.get("invoice_amount_max") or "").strip(),
        "invoice_status": (request.GET.get("invoice_status") or "").strip(),
        "order_from": (request.GET.get("order_from") or "").strip(),
        "order_to": (request.GET.get("order_to") or "").strip(),
        "order_count_min": (request.GET.get("order_count_min") or "").strip(),
        "order_count_max": (request.GET.get("order_count_max") or "").strip(),
        "service_category": (request.GET.get("service_category") or "").strip(),
        "order_status": (request.GET.get("order_status") or "").strip(),
    }

    invoice_from = _segment_parse_date(filters["invoice_from"])
    invoice_to = _segment_parse_date(filters["invoice_to"])
    invoice_amount_min = _segment_decimal(filters["invoice_amount_min"])
    invoice_amount_max = _segment_decimal(filters["invoice_amount_max"])
    order_from = _segment_parse_date(filters["order_from"])
    order_to = _segment_parse_date(filters["order_to"])
    order_count_min = _segment_int(filters["order_count_min"])
    order_count_max = _segment_int(filters["order_count_max"])

    customers = Customer.objects.filter(company=company)
    if filters["name"]:
        customers = customers.filter(Q(first_name__icontains=filters["name"]) | Q(last_name__icontains=filters["name"]))
    if filters["phone"]:
        customers = customers.filter(phone__icontains=filters["phone"])
    if filters["address"]:
        customers = customers.filter(Q(address__icontains=filters["address"]) | Q(orders__address__icontains=filters["address"])).distinct()

    has_invoice_filter = any([invoice_from, invoice_to, invoice_amount_min is not None, invoice_amount_max is not None, filters["invoice_status"]])
    has_order_filter = any([order_from, order_to, order_count_min is not None, order_count_max is not None, filters["service_category"], filters["order_status"]])

    rows = []
    for customer in customers.order_by("first_name", "last_name", "phone"):
        order_qs = _segment_order_queryset(company=company, customer=customer)
        invoice_qs = _segment_invoice_queryset(company=company, customer=customer)

        if order_from:
            order_qs = order_qs.filter(created_at__date__gte=order_from)
        if order_to:
            order_qs = order_qs.filter(created_at__date__lte=order_to)
        if filters["order_status"]:
            order_qs = order_qs.filter(status=filters["order_status"])
        if filters["service_category"]:
            try:
                order_qs = order_qs.filter(service_category_id=int(filters["service_category"]))
            except (TypeError, ValueError):
                order_qs = order_qs.none()

        if invoice_from:
            invoice_qs = invoice_qs.filter(created_at__date__gte=invoice_from)
        if invoice_to:
            invoice_qs = invoice_qs.filter(created_at__date__lte=invoice_to)
        if filters["invoice_status"]:
            invoice_qs = invoice_qs.filter(status=filters["invoice_status"])
        if invoice_amount_min is not None:
            invoice_qs = invoice_qs.filter(total_amount__gte=invoice_amount_min)
        if invoice_amount_max is not None:
            invoice_qs = invoice_qs.filter(total_amount__lte=invoice_amount_max)

        order_count = order_qs.count()
        invoice_count = invoice_qs.count()

        if has_order_filter and order_count == 0:
            continue
        if order_count_min is not None and order_count < order_count_min:
            continue
        if order_count_max is not None and order_count > order_count_max:
            continue
        if has_invoice_filter and invoice_count == 0:
            continue

        invoice_sum = invoice_qs.aggregate(total=Sum("total_amount")).get("total") or 0
        last_order = order_qs.order_by("-created_at").first() or _segment_order_queryset(company=company, customer=customer).order_by("-created_at").first()
        last_address = getattr(last_order, "address", "") if last_order else ""
        if not last_address:
            last_address = getattr(customer, "address", "") or ""

        rows.append({
            "customer_id": customer.id,
            "name": _segment_customer_name(customer),
            "phone": customer.phone,
            "email": customer.email,
            "order_count": order_count,
            "invoice_count": invoice_count,
            "invoice_sum": invoice_sum,
            "last_order_at": getattr(last_order, "created_at", None),
            "last_address": last_address,
        })

    return rows, filters


def _discount_make_candidate_view_rows(candidates):
    from types import SimpleNamespace

    rows = []
    for row in candidates or []:
        if isinstance(row, dict):
            customer_id = row.get("customer_id") or row.get("id") or ""
            name = row.get("name") or row.get("full_name") or row.get("customer_name") or "-"
            phone = row.get("phone") or row.get("customer_phone") or "-"
            order_count = row.get("order_count") or row.get("orders_count") or row.get("matching_order_count") or 0
            invoice_count = row.get("invoice_count") or row.get("invoices_count") or row.get("matching_invoice_count") or 0
            last_address = row.get("last_address") or row.get("address") or "-"
        else:
            customer = getattr(row, "customer", None)
            customer_id = getattr(row, "customer_id", None) or getattr(customer, "id", None) or getattr(row, "id", "")
            name = (
                getattr(row, "name", None)
                or getattr(row, "full_name", None)
                or getattr(row, "customer_name", None)
                or (getattr(customer, "get_full_name", lambda: "")() if customer else "")
                or getattr(customer, "phone", "")
                or getattr(row, "phone", "")
                or "-"
            )
            phone = getattr(row, "phone", None) or getattr(customer, "phone", None) or "-"
            order_count = getattr(row, "order_count", None) or getattr(row, "orders_count", None) or getattr(row, "matching_order_count", None) or 0
            invoice_count = getattr(row, "invoice_count", None) or getattr(row, "invoices_count", None) or getattr(row, "matching_invoice_count", None) or 0
            last_address = getattr(row, "last_address", None) or getattr(row, "address", None) or getattr(customer, "address", None) or "-"

        rows.append(SimpleNamespace(
            customer_id=customer_id,
            name=name,
            phone=phone,
            order_count=order_count,
            invoice_count=invoice_count,
            last_address=last_address,
        ))
    return rows

@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def discount_campaign_list(request: HttpRequest, **kwargs) -> HttpResponse:
    from .models import DiscountCampaign

    company = request.company
    campaigns = DiscountCampaign.objects.filter(company=company).order_by("-created_at")
    return render(request, "reports/discount_campaign_list.html", {
        "company": company,
        "campaigns": campaigns,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def discount_campaign_detail(request: HttpRequest, campaign_id: int, **kwargs) -> HttpResponse:
    from django.http import Http404
    from apps.sms.models import SMSOutbox
    from .models import DiscountCampaign, DiscountCode

    company = request.company
    campaign = DiscountCampaign.objects.filter(company=company, id=campaign_id).first()
    if campaign is None:
        raise Http404("کمپین پیدا نشد.")

    recipients = list(campaign.recipients.select_related("discount_code").all())
    sms_ids = [r.sms_outbox_id for r in recipients if r.sms_outbox_id]
    sms_map = {
        sms.id: sms.status
        for sms in SMSOutbox.objects.filter(company=company, id__in=sms_ids)
    }
    for recipient in recipients:
        recipient.sms_status = sms_map.get(recipient.sms_outbox_id or 0, "")

    used_count = DiscountCode.objects.filter(company=company, campaign=campaign, status=DiscountCode.Status.USED).count()

    return render(request, "reports/discount_campaign_detail.html", {
        "company": company,
        "campaign": campaign,
        "recipients": recipients,
        "used_count": used_count,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def discount_campaign_create_from_segment(request: HttpRequest, **kwargs) -> HttpResponse:
    from django.shortcuts import redirect
    from django.contrib import messages
    from django.utils import timezone
    import datetime

    from .discount_services import DEFAULT_DISCOUNT_MESSAGE_TEMPLATE, DiscountCampaignService
    from .models import DiscountCampaign

    company = request.company
    candidates, filters = _discount_segment_candidates(request, company)
    candidate_view_rows = _discount_make_candidate_view_rows(candidates)

    if request.method == "POST":
        required_errors = _discount_required_post_errors(request)
        if required_errors:
            for error in required_errors:
                messages.error(request, error)
            return redirect(request.path + ("?" + request.GET.urlencode() if request.GET else ""))

        selected_ids = {
            int(value)
            for value in request.POST.getlist("selected_customer_ids")
            if str(value).isdigit()
        }
        if not selected_ids:
            messages.error(request, "هیچ مشتری‌ای برای ارسال انتخاب نشده است.")
            return redirect(request.path + ("?" + request.GET.urlencode() if request.GET else ""))

        campaign = DiscountCampaignService.create_campaign(
            company=company,
            title=(request.POST.get("title") or "کمپین تخفیف هدفمند").strip(),
            source=DiscountCampaign.Source.SEGMENT,
            percent=_discount_decimal(request.POST.get("percent"), "20"),
            max_discount_rial=_discount_int(request.POST.get("max_discount_rial"), 300000),
            expires_at=_discount_parse_expiry(request.POST.get("expires_at")),
            recipients=candidates,
            selected_customer_ids=selected_ids,
            created_by=request.user,
            filter_snapshot=filters,
            message_template=DEFAULT_DISCOUNT_MESSAGE_TEMPLATE,
        )
        messages.success(request, "کمپین ساخته شد و پیامک‌ها در صف ارسال قرار گرفتند.")
        return redirect(f"/{company.code}/admin/reports/discount-campaigns/{campaign.id}/")

    default_expires = timezone.localdate() + datetime.timedelta(days=30)
    try:
        from apps.common.jalali import format_jalali_date
        default_expires_at = format_jalali_date(default_expires)
    except Exception:
        default_expires_at = default_expires.strftime("%Y/%m/%d")

    return render(request, "reports/discount_campaign_preview.html", {
        "company": company,
        "candidates": candidates,
        "candidate_view_rows": candidate_view_rows,
        "selected_customers": candidates,
        "selected_recipients": candidates,
        "target_customers": candidates,
        "campaign_customers": candidates,
        "campaign_recipients": candidates,
        "segment_results": candidates,
        "results": candidates,
        "discount_rows": candidates,
        "filters": filters,
        "default_title": "کمپین تخفیف هدفمند",
        "default_expires_at": default_expires_at,
        "default_message_template": DEFAULT_DISCOUNT_MESSAGE_TEMPLATE,
    })


@require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")
def discount_campaign_single_customer(request: HttpRequest, customer_id: int, **kwargs) -> HttpResponse:
    from django.http import Http404
    from django.shortcuts import redirect
    from django.contrib import messages
    from django.utils import timezone
    import datetime

    from apps.accounts.models import Customer
    from .discount_services import DEFAULT_DISCOUNT_MESSAGE_TEMPLATE, DiscountCampaignService
    from .models import DiscountCampaign

    company = request.company
    customer = Customer.objects.filter(company=company, id=customer_id).first()
    if customer is None:
        raise Http404("مشتری پیدا نشد.")

    customer_name = _segment_customer_name(customer)

    if request.method == "POST":
        required_errors = _discount_required_post_errors(request)
        if required_errors:
            for error in required_errors:
                messages.error(request, error)
            return redirect(request.path)

        row = {
            "customer_id": customer.id,
            "name": customer_name,
            "phone": customer.phone,
            "email": customer.email,
            "last_address": getattr(customer, "address", "") or "",
        }
        campaign = DiscountCampaignService.create_campaign(
            company=company,
            title=(request.POST.get("title") or f"کد تخفیف اختصاصی {customer_name}").strip(),
            source=DiscountCampaign.Source.SINGLE_CUSTOMER,
            percent=_discount_decimal(request.POST.get("percent"), "20"),
            max_discount_rial=_discount_int(request.POST.get("max_discount_rial"), 300000),
            expires_at=_discount_parse_expiry(request.POST.get("expires_at")),
            recipients=[row],
            selected_customer_ids={customer.id},
            created_by=request.user,
            filter_snapshot={"single_customer_id": customer.id},
            message_template=DEFAULT_DISCOUNT_MESSAGE_TEMPLATE,
        )
        messages.success(request, "کد تخفیف اختصاصی ساخته شد و پیامک آن در صف ارسال قرار گرفت.")
        return redirect(f"/{company.code}/admin/reports/discount-campaigns/{campaign.id}/")

    default_expires = timezone.localdate() + datetime.timedelta(days=30)
    try:
        from apps.common.jalali import format_jalali_date
        default_expires_at = format_jalali_date(default_expires)
    except Exception:
        default_expires_at = default_expires.strftime("%Y/%m/%d")

    return render(request, "reports/discount_single_customer.html", {
        "company": company,
        "customer": customer,
        "customer_name": customer_name,
        "default_expires_at": default_expires_at,
        "default_message_template": DEFAULT_DISCOUNT_MESSAGE_TEMPLATE,
    })
