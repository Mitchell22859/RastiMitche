"""Dashboard - URLs. Served under /<company_code>/admin/"""
from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.dashboard_home, name="home"),
]
