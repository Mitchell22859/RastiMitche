"""SMS URLs. Served under /<company_code>/admin/sms/"""
from django.urls import path

from . import views

app_name = "sms"

urlpatterns = [
    path("", views.sms_outbox_admin_list, name="outbox"),
    path("templates/", views.sms_template_list, name="template_list"),
    path("templates/create/", views.sms_template_create, name="template_create"),
    path("templates/<int:pk>/edit/", views.sms_template_edit, name="template_edit"),
    path("templates/<int:pk>/toggle/", views.sms_template_toggle, name="template_toggle"),
    path("outbox/", views.sms_outbox_admin_list, name="outbox_list"),
    path("outbox/<int:pk>/", views.sms_outbox_detail, name="outbox_detail"),
    path("outbox/<int:pk>/send-now/", views.sms_outbox_send_now, name="outbox_send_now"),
    path("outbox/bulk-retry/", views.sms_outbox_bulk_retry, name="outbox_bulk_retry"),
    path("diagnostics/", views.sms_diagnostics, name="diagnostics"),
]
