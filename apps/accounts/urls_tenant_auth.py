"""
Accounts - Tenant Auth URLs.

Served under /<company_code>/login/
"""
from django.urls import path

from . import views

app_name = "accounts_auth"

urlpatterns = [
    path("", views.tenant_login, name="login"),
    path("logout/", views.tenant_logout, name="logout"),
]
