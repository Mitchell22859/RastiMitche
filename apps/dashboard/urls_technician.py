"""
Dashboard - Technician URLs.

Served under /<company_code>/technician/
"""
from django.urls import path

from . import views

app_name = "dashboard_technician"

urlpatterns = [
    path("", views.technician_home, name="home"),
]
