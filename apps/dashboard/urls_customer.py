"""
Dashboard - Customer URLs.

Served under /<company_code>/customer/
"""
from django.urls import path

from . import views

app_name = "dashboard_customer"

urlpatterns = [
    path("", views.customer_home, name="home"),
]
