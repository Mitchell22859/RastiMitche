"""
API - URL Configuration.

Routes:
  Auth API: /api/auth/...
  Tenant API: /api/<company_code>/...
  Platform API: /api/platform/...

Tenant middleware resolves request.company for /api/<company_code>/ routes.
"""
from django.urls import path

from . import views
from .auth_views import LoginAPI, TokenRefreshAPI, MeAPI, LogoutAPI, ChangePasswordAPI

app_name = "api"

# Auth API routes (served under /api/auth/)
auth_urlpatterns = [
    path("login/", LoginAPI.as_view(), name="auth-login"),
    path("token/refresh/", TokenRefreshAPI.as_view(), name="auth-token-refresh"),
    path("me/", MeAPI.as_view(), name="auth-me"),
    path("logout/", LogoutAPI.as_view(), name="auth-logout"),
    path("change-password/", ChangePasswordAPI.as_view(), name="auth-change-password"),
]

# Tenant API routes (served under /api/<company_code>/)
tenant_urlpatterns = [
    path("orders/", views.OrderListAPI.as_view(), name="orders-list"),
    path("orders/<int:order_id>/", views.OrderDetailAPI.as_view(), name="orders-detail"),
    path("invoices/", views.InvoiceListAPI.as_view(), name="invoices-list"),
    path("notifications/", views.NotificationListAPI.as_view(), name="notifications-list"),
    path("services/", views.CompanyServiceListAPI.as_view(), name="services-list"),
    path("service-requests/", views.ServiceRequestListAPI.as_view(), name="service-requests-list"),
    path("customers/", views.CustomerListAPI.as_view(), name="customers-list"),
    path("customers/<int:customer_id>/", views.CustomerDetailAPI.as_view(), name="customers-detail"),
    path("technicians/", views.TechnicianListAPI.as_view(), name="technicians-list"),
    path("dashboard/", views.DashboardAPI.as_view(), name="dashboard"),
]

# Platform API routes (served under /api/platform/)
platform_urlpatterns = [
    path("companies/", views.PlatformCompanyListAPI.as_view(), name="platform-companies"),
    path("reports/", views.PlatformReportsAPI.as_view(), name="platform-reports"),
]
