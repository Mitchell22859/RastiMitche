"""
Accounts - Views.

Thin views for authentication. All business logic delegated to services.
All permission logic uses decorators from permissions.py.
"""
from django.contrib.auth import authenticate
from django.http import HttpRequest, HttpResponse, HttpResponsePermanentRedirect
from django.shortcuts import redirect, render

from .forms import PlatformLoginForm, TenantLoginForm
from .models import UserRole
from .services import AuthenticationService, RedirectService


# =============================================================================
# UNIFIED LOGIN VIEW (serves /login/)
# =============================================================================


def unified_login(request: HttpRequest) -> HttpResponse:
    """
    Single unified login page for ALL user roles.

    GET: Display login form.
    POST: Authenticate any user (platform owner, admin, technician, customer),
          detect role, redirect to correct dashboard.

    Username is the login identifier (globally unique).
    """
    # Already authenticated → redirect to appropriate dashboard
    if request.user.is_authenticated:
        url = RedirectService.get_post_login_url(user=request.user)
        return redirect(url)

    error = ""
    username_value = ""

    if request.method == "POST":
        username = request.POST.get("username", "").strip().lower()
        password = request.POST.get("password", "")
        username_value = username

        if not username or not password:
            error = "نام کاربری و رمز عبور الزامی است."
        else:
            user = authenticate(request, username=username, password=password)

            if user is None:
                error = "نام کاربری یا رمز عبور اشتباه است."
            elif not user.is_active:
                error = "حساب کاربری شما توسط مدیر شرکت غیرفعال شده است."
            elif user.company and not user.company.is_active:
                error = "دسترسی پنل شرکت توسط مالک پلتفرم محدود شده است. با پشتیبانی تماس بگیرید."
            else:
                needs_pw_change = (
                    getattr(user, "must_change_password", False)
                    or user.check_password("123456")
                )
                AuthenticationService.login_user(request=request, user=user)
                if needs_pw_change:
                    return redirect("/account/change-password-required/")
                # Redirect to ?next= if provided, otherwise role-based
                next_url = request.POST.get("next") or request.GET.get("next")
                if next_url and next_url.startswith("/"):
                    return redirect(next_url)
                url = RedirectService.get_post_login_url(user=user)
                return redirect(url)

    return render(request, "accounts/unified_login.html", {
        "error": error,
        "username_value": username_value,
        "next": request.GET.get("next", ""),
    })


def unified_logout(request: HttpRequest) -> HttpResponse:
    """Logout for any user. Redirects to unified login."""
    AuthenticationService.logout_user(request=request)
    return redirect("/login/")


# =============================================================================
# PLATFORM AUTHENTICATION VIEWS
# =============================================================================


def platform_login(request: HttpRequest) -> HttpResponse:
    """
    Platform owner login page at /loginlogin/.

    GET: Display login form.
    POST: Authenticate platform owner, redirect to dashboard.
    """
    # Already logged in platform owner → redirect to dashboard
    if request.user.is_authenticated:
        from .permissions import is_platform_owner
        if is_platform_owner(request.user):
            return redirect("/loginlogin/dashboard/")

    error = ""
    form = PlatformLoginForm()

    if request.method == "POST":
        form = PlatformLoginForm(request.POST)
        if form.is_valid():
            user, error = AuthenticationService.authenticate_platform_user(
                request=request,
                phone=form.cleaned_data["phone"],
                password=form.cleaned_data["password"],
            )
            if user:
                AuthenticationService.login_user(request=request, user=user)
                return redirect("/loginlogin/dashboard/")

    return render(request, "accounts/platform_login.html", {
        "form": form,
        "error": error,
    })


def platform_logout(request: HttpRequest) -> HttpResponse:
    """Logout for platform owners."""
    AuthenticationService.logout_user(request=request)
    return redirect("/loginlogin/")


# =============================================================================
# TENANT AUTHENTICATION VIEWS
# =============================================================================


def tenant_login(request: HttpRequest, **kwargs) -> HttpResponse:
    """
    Legacy tenant login at /<company_code>/login/.
    Redirects to unified /login/?company=<code> for backward compatibility.
    """
    company = getattr(request, "company", None)
    code = company.code if company else ""
    return HttpResponsePermanentRedirect(f"/login/?company={code}")


def tenant_logout(request: HttpRequest, **kwargs) -> HttpResponse:
    """Logout for tenant users. Redirects to unified login."""
    AuthenticationService.logout_user(request=request)
    return redirect("/login/")
