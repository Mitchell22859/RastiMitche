"""
Platform Core - URL Configuration.

These URLs are served under /owner-platform/ prefix.
Only accessible by PLATFORM_OWNER role.
"""
from django.urls import path

from apps.accounts import views as auth_views

from . import views
from . import views_comm_templates
from . import views_messages
from . import views_payment_gateways
from . import views_platform_sms
from . import views_sms_billing
from . import views_sms_template_requests

app_name = "platform_core"

urlpatterns = [
    # Root of /owner-platform/ → redirect to dashboard
    path("", views.platform_dashboard, name="root"),
    path("logout/", auth_views.unified_logout, name="logout"),

    # Dashboard + Reports
    path("dashboard/", views.platform_dashboard, name="dashboard"),
    path("reports/", views.platform_reports, name="reports"),

    # Message Center
    path("messages/", views_messages.message_index, name="messages"),
    path("messages/inbox/", views_messages.message_inbox, name="messages_inbox"),
    path("messages/outbox/", views_messages.message_outbox, name="messages_outbox"),
    path("messages/create/", views_messages.message_create, name="messages_create"),
    path("messages/<int:message_id>/", views_messages.message_detail, name="messages_detail"),

    # SMS Billing
    path("sms-billing/", views_sms_billing.sms_billing_index, name="sms_billing"),
    path("sms-billing/settings/", views_sms_billing.sms_billing_settings, name="sms_billing_settings"),
    path("sms-billing/companies/", views_sms_billing.sms_billing_companies, name="sms_billing_companies"),
    path("sms-billing/transactions/", views_sms_billing.sms_billing_transactions, name="sms_billing_transactions"),
    path("sms-billing/invoices/", views_sms_billing.sms_billing_invoices, name="sms_billing_invoices"),
    path("sms-billing/invoices/<int:invoice_id>/", views_sms_billing.sms_billing_invoice_detail, name="sms_billing_invoice_detail"),
    path("sms-billing/invoices/<int:invoice_id>/mark-paid/", views_sms_billing.sms_billing_invoice_mark_paid, name="sms_billing_invoice_mark_paid"),

    # Communication Templates
    path("communication-templates/", views_comm_templates.comm_template_list, name="comm_templates"),
    path("communication-templates/create/", views_comm_templates.comm_template_create, name="comm_template_create"),
    path("communication-templates/<int:template_id>/", views_comm_templates.comm_template_detail, name="comm_template_detail"),
    path("communication-templates/<int:template_id>/edit/", views_comm_templates.comm_template_edit, name="comm_template_edit"),

    # Payment Gateways
    path("payment-gateways/", views_payment_gateways.platform_gateway_index, name="platform_gateways"),
    path("payment-gateways/settings/", views_payment_gateways.platform_gateway_settings, name="platform_gateway_settings"),
    path("payment-gateways/test/", views_payment_gateways.platform_gateway_test, name="platform_gateway_test"),

    # Platform SMS Outbox + Global SMS Settings
    path("platform-sms/", views_platform_sms.platform_sms_index, name="platform_sms"),
    path("platform-sms/message-types/", views_platform_sms.platform_sms_message_types, name="platform_sms_message_types"),
    path("platform-sms/provider/", views_platform_sms.platform_sms_provider_settings, name="platform_sms_provider"),
    path("platform-sms/outbox/", views_platform_sms.platform_sms_outbox, name="platform_sms_outbox"),
    path("platform-sms/outbox/process/", views_platform_sms.platform_sms_process_outbox, name="platform_sms_process_outbox"),
    path("platform-sms/outbox/<int:sms_id>/", views_platform_sms.platform_sms_outbox_detail, name="platform_sms_outbox_detail"),
    path("platform-sms/outbox/<int:sms_id>/send-now/", views_platform_sms.platform_sms_outbox_send_now, name="platform_sms_outbox_send_now"),

    # SMS Template Change Requests (Phase 19C)
    path("sms-template-requests/", views_sms_template_requests.request_list, name="owner_sms_template_requests"),
    path("sms-template-requests/<int:request_id>/", views_sms_template_requests.request_detail, name="owner_sms_template_request_detail"),
    path("sms-template-requests/<int:request_id>/approve/", views_sms_template_requests.request_approve, name="owner_sms_template_request_approve"),
    path("sms-template-requests/<int:request_id>/reject/", views_sms_template_requests.request_reject, name="owner_sms_template_request_reject"),

    # Company Management
    path("companies/", views.company_list, name="companies"),
    path("companies/create/", views.company_create, name="company_create"),
    path("companies/<int:company_id>/", views.company_detail, name="company_detail"),
    path("companies/<int:company_id>/edit/", views.company_edit, name="company_edit"),
    path("companies/<int:company_id>/activate/", views.company_activate, name="company_activate"),
    path("companies/<int:company_id>/deactivate/", views.company_deactivate, name="company_deactivate"),

    # Company-specific communication templates (from company detail)
    path("companies/<int:company_id>/templates/", views_comm_templates.company_templates_list, name="company_comm_templates"),
    path("companies/<int:company_id>/templates/create/", views_comm_templates.company_template_create, name="company_comm_template_create"),
    path("companies/<int:company_id>/templates/<int:template_id>/edit/", views_comm_templates.company_template_edit, name="company_comm_template_edit"),
    path("companies/<int:company_id>/templates/<int:template_id>/reset/", views_comm_templates.company_template_reset, name="company_comm_template_reset"),

    # Plan Management
    path("plans/", views.plan_list, name="plans"),
    path("plans/create/", views.plan_create, name="plan_create"),
    path("plans/<int:plan_id>/edit/", views.plan_edit, name="plan_edit"),

    # Subscription Management
    path("subscriptions/", views.subscription_list, name="subscriptions"),
    path("subscriptions/create/", views.subscription_create, name="subscription_create"),
    path("subscriptions/<int:subscription_id>/edit/", views.subscription_edit, name="subscription_edit"),
    path("subscriptions/<int:subscription_id>/activate/", views.subscription_activate, name="subscription_activate"),
    path("subscriptions/<int:subscription_id>/cancel/", views.subscription_cancel, name="subscription_cancel"),
]
