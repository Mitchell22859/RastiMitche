"""
Rasti Service - Root URL Configuration.

URL Routing Strategy (Phase: Unified Login):
=============================================

1. Public pages (no auth):
   - /                    -> Landing page
   - /features/           -> Features
   - /pricing/            -> Pricing
   - /about/              -> About
   - /contact/            -> Contact
   - /register/           -> Company registration
   - /login/              -> Unified login (ALL roles)
   - /logout/             -> Unified logout
   - /i/<public_code>/    -> Short public invoice link (no auth)

2. Platform owner panel:
   - /owner-platform/     -> Platform owner dashboard & management

3. Tenant-level (company-scoped):
   - /<company_code>/admin/    -> Company admin/operator panel
   - /<company_code>/tech/     -> Technician panel
   - /<company_code>/customer/ -> Customer panel

4. Legacy backward-compatible redirects:
   - /loginlogin/*         -> /owner-platform/* (or /login/)
   - /<code>/login/        -> /login/?company=<code>

5. REST API:
   - /api/auth/*
   - /api/platform/*
   - /api/<company_code>/*
"""
from django.contrib import admin
from django.http import HttpResponse, HttpResponsePermanentRedirect, HttpResponseRedirect
from django.urls import include, path

from apps.accounts import views as auth_views
from apps.api.urls import auth_urlpatterns, platform_urlpatterns, tenant_urlpatterns
from apps.platform_core.health import health_check, health_db_check

# Public availability check API
from apps.public import api_views as public_api


# =============================================================================
# HELPER VIEWS
# =============================================================================

def rasti_favicon_view(request):
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="14" fill="#2563eb"/><text x="32" y="43" font-size="34" text-anchor="middle" fill="white" font-family="Arial">R</text></svg>'
    return HttpResponse(svg, content_type="image/svg+xml")


# =============================================================================
# BACKWARD-COMPATIBLE REDIRECTS
# =============================================================================

def redirect_loginlogin_root(request):
    """Redirect /loginlogin/ to /login/ (or /owner-platform/ if authenticated owner)."""
    if request.user.is_authenticated:
        from apps.accounts.models import UserRole
        if getattr(request.user, "role", None) == UserRole.PLATFORM_OWNER:
            return HttpResponsePermanentRedirect("/owner-platform/dashboard/")
    return HttpResponsePermanentRedirect("/login/")


def redirect_loginlogin_sub(request, path=""):
    """Redirect /loginlogin/<path> to /owner-platform/<path>."""
    if request.user.is_authenticated:
        from apps.accounts.models import UserRole
        if getattr(request.user, "role", None) == UserRole.PLATFORM_OWNER:
            return HttpResponsePermanentRedirect(f"/owner-platform/{path}")
    return HttpResponseRedirect("/login/")


def redirect_tenant_login(request, **kwargs):
    """Redirect /<company_code>/login/ to /login/?company=<company_code>."""
    company = getattr(request, "company", None)
    code = company.code if company else kwargs.get("company_code", "")
    return HttpResponsePermanentRedirect(f"/login/?company={code}")


# =============================================================================
# URL PATTERNS
# =============================================================================

urlpatterns = [
    path("favicon.ico", rasti_favicon_view, name="favicon"),

    # =========================================================================
    # HEALTH CHECKS (exempt from tenant resolution)
    # =========================================================================
    path("health/", health_check, name="health"),
    path("health/db/", health_db_check, name="health-db"),

    # =========================================================================
    # UNIFIED AUTH (exempt from tenant resolution)
    # =========================================================================
    path("login/", auth_views.unified_login, name="login"),
    path("logout/", auth_views.unified_logout, name="logout"),
    path("password-reset/", include("apps.accounts.urls_password_reset")),

    # =========================================================================
    # PUBLIC PAGES (exempt from tenant resolution)
    # =========================================================================
    path("", include("apps.public.urls")),

    # =========================================================================
    # PLATFORM OWNER PANEL (exempt from tenant resolution)
    # =========================================================================
    path("owner-platform/", include("apps.platform_core.urls")),

    # =========================================================================
    # DJANGO ADMIN
    # =========================================================================
    path("admin/", admin.site.urls),

    # =========================================================================
    # SHORT PUBLIC INVOICE LINK (no auth, globally unique public_code)
    # =========================================================================
    path("i/<str:public_code>/", include("apps.invoices.urls_public_short")),

    # =========================================================================
    # BACKWARD-COMPATIBLE REDIRECTS
    # =========================================================================
    path("loginlogin/", redirect_loginlogin_root, name="legacy_loginlogin"),
    path("loginlogin/<path:path>", redirect_loginlogin_sub, name="legacy_loginlogin_sub"),

    # =========================================================================
    # REST API ROUTES
    # =========================================================================
    path("api/public/check-username/", public_api.check_username, name="api-check-username"),
    path("api/public/check-company-code/", public_api.check_company_code, name="api-check-company-code"),
    path("api/public/check-admin-email/", public_api.check_admin_email, name="api-check-admin-email"),
    path("api/public/check-company-email/", public_api.check_company_email, name="api-check-company-email"),
    path("api/auth/", include((auth_urlpatterns, "api"), namespace="api-auth")),
    path("api/platform/", include((platform_urlpatterns, "api"), namespace="api-platform")),
    path("api/<slug:company_code>/", include((tenant_urlpatterns, "api"), namespace="api-tenant")),

    # =========================================================================
    # TENANT-LEVEL ROUTES (tenant middleware resolves company)
    # =========================================================================
    path("<slug:company_code>/", include("apps.tenants.urls")),
]

# Serve media files in development
from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
