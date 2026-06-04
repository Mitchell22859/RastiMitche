"""
Platform Core - Views.

Platform owner management views for companies, plans, subscriptions.
All views require PLATFORM_OWNER role.
"""
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import redirect, render

from apps.accounts.permissions import require_platform_owner
from apps.dashboard.selectors import PlatformDashboardSelector
from apps.reports.selectors import PlatformReportSelector
from apps.tenants.models import Company

from .forms import CompanyCreateForm, CompanyEditForm, PlanForm, SubscriptionForm
from .models import Plan, Subscription
from .selectors import PlanSelector, PlatformCompanySelector, SubscriptionSelector


# =============================================================================
# DASHBOARD + REPORTS
# =============================================================================


@require_platform_owner
def platform_dashboard(request: HttpRequest) -> HttpResponse:
    """Platform owner dashboard with global stats."""
    stats = PlatformDashboardSelector.get_stats()
    recent_companies = PlatformDashboardSelector.get_recent_companies()
    return render(request, "platform_core/dashboard.html", {
        "stats": stats, "recent_companies": recent_companies,
    })


@require_platform_owner
def platform_reports(request: HttpRequest) -> HttpResponse:
    """Platform-level reports."""
    company_summary = PlatformReportSelector.company_summary()
    subscription_summary = PlatformReportSelector.subscription_summary()
    usage = PlatformReportSelector.tenant_usage_summary()
    return render(request, "platform_core/reports.html", {
        "company_summary": company_summary,
        "subscription_summary": subscription_summary,
        "usage": usage,
    })


# =============================================================================
# COMPANY MANAGEMENT
# =============================================================================


@require_platform_owner
def company_list(request: HttpRequest) -> HttpResponse:
    """List all companies."""
    companies = PlatformCompanySelector.get_all()
    return render(request, "platform_core/company_list.html", {"companies": companies})


@require_platform_owner
def company_create(request: HttpRequest) -> HttpResponse:
    """Create a new company."""
    error = ""
    if request.method == "POST":
        form = CompanyCreateForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]
            if Company.objects.filter(code=code).exists():
                error = "این کد قبلا استفاده شده."
            else:
                company = Company.objects.create(
                    name=form.cleaned_data["name"],
                    code=code,
                    slug=code,
                    email=form.cleaned_data.get("email", ""),
                    phone=form.cleaned_data.get("phone", ""),
                    address=form.cleaned_data.get("address", ""),
                    is_active=True,
                )
                try:
                    from apps.sms.provisioning import provision_company_communication_defaults

                    provision_company_communication_defaults(company)
                except Exception:
                    # Provisioning must never break company creation.
                    pass
                return redirect("/owner-platform/companies/")
    else:
        form = CompanyCreateForm()
    return render(request, "platform_core/company_form.html", {
        "form": form, "error": error, "is_edit": False,
    })


@require_platform_owner
def company_detail(request: HttpRequest, company_id: int) -> HttpResponse:
    """Company detail with stats."""
    company = PlatformCompanySelector.get_by_id(company_id=company_id)
    if not company:
        raise Http404("شرکت یافت نشد.")
    stats = PlatformCompanySelector.get_company_stats(company=company)
    subscription = SubscriptionSelector.get_for_company(company_id=company.id)
    return render(request, "platform_core/company_detail.html", {
        "company": company, "stats": stats, "subscription": subscription,
    })


@require_platform_owner
def company_edit(request: HttpRequest, company_id: int) -> HttpResponse:
    """Edit a company."""
    company = PlatformCompanySelector.get_by_id(company_id=company_id)
    if not company:
        raise Http404("شرکت یافت نشد.")
    error = ""
    if request.method == "POST":
        form = CompanyEditForm(request.POST)
        if form.is_valid():
            company.name = form.cleaned_data["name"]
            company.email = form.cleaned_data.get("email", "")
            company.phone = form.cleaned_data.get("phone", "")
            company.address = form.cleaned_data.get("address", "")
            company.save()
            return redirect(f"/owner-platform/companies/{company.id}/")
    else:
        form = CompanyEditForm(initial={
            "name": company.name, "email": company.email,
            "phone": company.phone, "address": company.address,
        })
    return render(request, "platform_core/company_form.html", {
        "form": form, "error": error, "is_edit": True, "company": company,
    })


@require_platform_owner
def company_activate(request: HttpRequest, company_id: int) -> HttpResponse:
    """Activate a company."""
    company = PlatformCompanySelector.get_by_id(company_id=company_id)
    if not company:
        raise Http404("شرکت یافت نشد.")
    if request.method == "POST":
        company.is_active = True
        company.save(update_fields=["is_active", "updated_at"])

        try:
            from apps.sms.provisioning import provision_company_communication_defaults

            provision_company_communication_defaults(company)
        except Exception:
            # Provisioning must never break activation.
            pass

        try:
            from apps.notifications.event_catalog import EventKey
            from apps.notifications.services_events import NotificationEventService

            NotificationEventService.emit(
                event_key=EventKey.COMPANY_ACTIVATED,
                company=company,
                actor=request.user,
                target=company,
                payload={
                    "company_name": company.name,
                    "company_code": company.code,
                },
                dispatch=True,
            )
        except Exception:
            pass

    return redirect(f"/owner-platform/companies/{company.id}/")


@require_platform_owner
def company_deactivate(request: HttpRequest, company_id: int) -> HttpResponse:
    """Deactivate a company."""
    company = PlatformCompanySelector.get_by_id(company_id=company_id)
    if not company:
        raise Http404("شرکت یافت نشد.")
    if request.method == "POST":
        company.is_active = False
        company.save(update_fields=["is_active", "updated_at"])
    return redirect(f"/owner-platform/companies/{company.id}/")


# =============================================================================
# PLAN MANAGEMENT
# =============================================================================


@require_platform_owner
def plan_list(request: HttpRequest) -> HttpResponse:
    """List all plans."""
    plans = PlanSelector.get_all()
    return render(request, "platform_core/plan_list.html", {"plans": plans})


@require_platform_owner
def plan_create(request: HttpRequest) -> HttpResponse:
    """Create a plan."""
    error = ""
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            code = form.cleaned_data["code"]
            if Plan.objects.filter(code=code).exists():
                error = "این کد قبلا استفاده شده."
            else:
                Plan.objects.create(
                    name=form.cleaned_data["name"],
                    code=code,
                    description=form.cleaned_data.get("description", ""),
                    price_monthly=form.cleaned_data["price_monthly"],
                    price_yearly=form.cleaned_data.get("price_yearly") or 0,
                    max_users=form.cleaned_data["max_users"],
                    max_technicians=form.cleaned_data["max_technicians"],
                    max_orders_per_month=form.cleaned_data["max_orders_per_month"],
                    is_active=form.cleaned_data.get("is_active", True),
                )
                return redirect("/owner-platform/plans/")
    else:
        form = PlanForm()
    return render(request, "platform_core/plan_form.html", {
        "form": form, "error": error, "is_edit": False,
    })


@require_platform_owner
def plan_edit(request: HttpRequest, plan_id: int) -> HttpResponse:
    """Edit a plan."""
    plan = PlanSelector.get_by_id(plan_id=plan_id)
    if not plan:
        raise Http404("پلن یافت نشد.")
    error = ""
    if request.method == "POST":
        form = PlanForm(request.POST)
        if form.is_valid():
            plan.name = form.cleaned_data["name"]
            plan.code = form.cleaned_data["code"]
            plan.description = form.cleaned_data.get("description", "")
            plan.price_monthly = form.cleaned_data["price_monthly"]
            plan.price_yearly = form.cleaned_data.get("price_yearly") or 0
            plan.max_users = form.cleaned_data["max_users"]
            plan.max_technicians = form.cleaned_data["max_technicians"]
            plan.max_orders_per_month = form.cleaned_data["max_orders_per_month"]
            plan.is_active = form.cleaned_data.get("is_active", True)
            plan.save()
            return redirect("/owner-platform/plans/")
    else:
        form = PlanForm(initial={
            "name": plan.name, "code": plan.code, "description": plan.description,
            "price_monthly": plan.price_monthly, "price_yearly": plan.price_yearly,
            "max_users": plan.max_users, "max_technicians": plan.max_technicians,
            "max_orders_per_month": plan.max_orders_per_month, "is_active": plan.is_active,
        })
    return render(request, "platform_core/plan_form.html", {
        "form": form, "error": error, "is_edit": True, "plan": plan,
    })


# =============================================================================
# SUBSCRIPTION MANAGEMENT
# =============================================================================


@require_platform_owner
def subscription_list(request: HttpRequest) -> HttpResponse:
    """List all subscriptions."""
    subscriptions = SubscriptionSelector.get_all()
    return render(request, "platform_core/subscription_list.html", {"subscriptions": subscriptions})


@require_platform_owner
def subscription_create(request: HttpRequest) -> HttpResponse:
    """Create a subscription."""
    error = ""
    companies = Company.objects.filter(is_active=True)
    plans = PlanSelector.get_active()

    if request.method == "POST":
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            company_id = form.cleaned_data["company_id"]
            if Subscription.objects.filter(company_id=company_id).exists():
                error = "این شرکت قبلا اشتراک دارد."
            else:
                Subscription.objects.create(
                    company_id=company_id,
                    plan_id=form.cleaned_data["plan_id"],
                    status=form.cleaned_data["status"],
                    started_at=form.cleaned_data["started_at"],
                    expires_at=form.cleaned_data["expires_at"],
                )
                return redirect("/owner-platform/subscriptions/")
    else:
        form = SubscriptionForm()

    return render(request, "platform_core/subscription_form.html", {
        "form": form, "error": error, "is_edit": False,
        "companies": companies, "plans": plans,
    })


@require_platform_owner
def subscription_edit(request: HttpRequest, subscription_id: int) -> HttpResponse:
    """Edit a subscription."""
    sub = SubscriptionSelector.get_by_id(subscription_id=subscription_id)
    if not sub:
        raise Http404("اشتراک یافت نشد.")
    error = ""
    companies = Company.objects.filter(is_active=True)
    plans = PlanSelector.get_active()

    if request.method == "POST":
        form = SubscriptionForm(request.POST)
        if form.is_valid():
            sub.plan_id = form.cleaned_data["plan_id"]
            sub.status = form.cleaned_data["status"]
            sub.started_at = form.cleaned_data["started_at"]
            sub.expires_at = form.cleaned_data["expires_at"]
            sub.save()
            return redirect("/owner-platform/subscriptions/")
    else:
        form = SubscriptionForm(initial={
            "company_id": sub.company_id, "plan_id": sub.plan_id,
            "status": sub.status, "started_at": sub.started_at.strftime("%Y-%m-%d %H:%M") if sub.started_at else "",
            "expires_at": sub.expires_at.strftime("%Y-%m-%d %H:%M") if sub.expires_at else "",
        })

    return render(request, "platform_core/subscription_form.html", {
        "form": form, "error": error, "is_edit": True, "sub": sub,
        "companies": companies, "plans": plans,
    })


@require_platform_owner
def subscription_activate(request: HttpRequest, subscription_id: int) -> HttpResponse:
    """Activate a subscription."""
    sub = SubscriptionSelector.get_by_id(subscription_id=subscription_id)
    if not sub:
        raise Http404("اشتراک یافت نشد.")
    if request.method == "POST":
        sub.status = Subscription.Status.ACTIVE
        sub.save(update_fields=["status", "updated_at"])
    return redirect("/owner-platform/subscriptions/")


@require_platform_owner
def subscription_cancel(request: HttpRequest, subscription_id: int) -> HttpResponse:
    """Cancel a subscription."""
    sub = SubscriptionSelector.get_by_id(subscription_id=subscription_id)
    if not sub:
        raise Http404("اشتراک یافت نشد.")
    if request.method == "POST":
        sub.status = Subscription.Status.CANCELLED
        sub.save(update_fields=["status", "updated_at"])
    return redirect("/owner-platform/subscriptions/")
