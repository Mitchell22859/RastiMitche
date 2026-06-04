"""
Technician order URLs.

Served under /<company_code>/tech/orders/.
These routes are reserved for technician workbench actions.
"""
from django.urls import path

from . import views

app_name = "orders_technician"

urlpatterns = [
    path("available/", views.technician_available_orders, name="available"),
    path("my/", views.technician_my_orders, name="my_orders"),
    path("<int:order_id>/invoice/create/", views.technician_invoice_create, name="invoice_create"),
    path("<int:order_id>/", views.order_detail, name="detail"),
    path("<int:order_id>/accept/", views.order_accept, name="accept"),
    path("<int:order_id>/complete/", views.order_complete, name="complete"),
    path("<int:order_id>/cancel/", views.order_cancel, name="cancel"),
    path("<int:order_id>/status/", views.technician_status_update, name="status_update"),
]
