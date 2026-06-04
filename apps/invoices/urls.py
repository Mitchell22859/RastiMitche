"""
Invoices - URL Configuration.

Served under /<company_code>/invoices/
"""
from django.urls import path

from . import views

app_name = "invoices"

urlpatterns = [
    path("public/<str:public_code>/", views.public_invoice_detail, name="public_detail"),
    path("public/<str:public_code>/discount/", views.public_invoice_apply_discount, name="public_apply_discount"),
    path("public/<str:public_code>/print/", views.invoice_print, name="print"),
    path("", views.invoice_list, name="list"),
    path("<int:invoice_id>/", views.invoice_detail, name="detail"),
    path("<int:invoice_id>/pay/", views.invoice_pay, name="pay"),
    path("<int:invoice_id>/discount/", views.invoice_apply_discount, name="apply_discount"),
]
