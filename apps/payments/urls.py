"""
Payments - URL Configuration.

Served under /<company_code>/payments/
"""
from django.urls import path

from . import views

app_name = "payments"

urlpatterns = [
    path("", views.payment_list, name="list"),
    path("callback/", views.payment_callback, name="callback"),
]
