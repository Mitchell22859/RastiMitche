from django.urls import path
from . import views_technician

app_name = "invoices_technician"

urlpatterns = [
    path("", views_technician.technician_invoice_list, name="list"),
    path("order/<int:order_id>/create/", views_technician.technician_invoice_create, name="create_from_order"),
    path("<int:invoice_id>/cash-paid/", views_technician.technician_invoice_mark_cash_paid, name="cash_paid"),
    path("<int:invoice_id>/", views_technician.technician_invoice_detail, name="detail"),
]




