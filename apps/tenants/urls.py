"""
Tenants - URL Configuration.

These URLs are served under /<company_code>/ prefix.
The tenant middleware has already resolved request.company by this point.

URL Structure (Phase 24 cleanup):
- /<company_code>/              → Public/customer-facing pages
- /<company_code>/admin/...     → Company admin/operator panel
- /<company_code>/tech/...      → Technician panel
- /<company_code>/login/        → Tenant authentication

REMOVED (Phase 24):
- /<company_code>/orders/       → Was duplicating tech/admin actions at public level
- /<company_code>/reports/      → Was exposing admin reports at public level
- /<company_code>/notifications/→ Was duplicating role-specific notification routes

These legacy paths now redirect to the correct role-specific panel.
"""
from django.urls import include, path

from . import views, views_admin, views_branding
from apps.payouts import views as payouts_views
from apps.payouts import views_split_snapshots as split_snapshot_views
from . import views_merchant_profile as merchant_profile_views
from apps.platform_core import views_tenant_sms_credit as tenant_sms_views
from apps.platform_core import views_tenant_comm_settings as tenant_comm_views
from .views_redirects import (
    legacy_notifications_redirect,
    legacy_orders_catch_all,
    legacy_orders_redirect,
    legacy_reports_redirect,
)
from apps.platform_core import views_tenant_payment_gateway as tenant_pg_views
from . import views_financial_reports as financial_report_views

app_name = "tenants"

urlpatterns = [
    # =========================================================================
    # PUBLIC PAGES (no auth required)
    # =========================================================================
    path("", views.company_home, name="home"),
    path("request/", views.service_request_view, name="request"),
    path("request/status/", views.service_request_status, name="request_status"),

    # =========================================================================
    # AUTHENTICATION
    # =========================================================================
    path("login/", include("apps.accounts.urls_tenant_auth")),

    # =========================================================================
    # ADMIN / OPERATOR PANEL (/<company_code>/admin/...)
    # =========================================================================

    # Admin dashboard
    path("admin/", include("apps.dashboard.urls")),

    # Admin: Company page and settings
    path("admin/page/", views_admin.admin_page_edit, name="admin_page"),
    path("admin/settings/", views_admin.admin_company_settings, name="admin_company_settings"),
    path("admin/settings/notifications/", views_admin.admin_notification_settings, name="admin_notification_settings"),
    path("admin/settings/operators/", views_admin.admin_operator_list, name="admin_operator_list"),

    # Admin: Payment Gateway
    path("admin/payment-gateway/", tenant_pg_views.tenant_gateway_settings, name="admin_payment_gateway"),
    path("admin/payment-gateway/test/", tenant_pg_views.tenant_gateway_test, name="admin_payment_gateway_test"),

    # Admin: Merchant/KYC Profile (Payment P5)
    path("admin/payment/merchant-profile/", merchant_profile_views.merchant_profile_view, name="admin_merchant_profile"),
    path("admin/payment/merchant-profile/edit-request/", merchant_profile_views.merchant_profile_edit_request_view, name="admin_merchant_profile_edit_request"),
    path("admin/payment/merchant-profile/document/<str:field_name>/", merchant_profile_views.serve_profile_document, name="admin_merchant_profile_document"),

    # Admin: Services CRUD

    # Admin: Base data management
    path("admin/base-data/", views_admin.admin_base_data_home, name="admin_base_data"),

    path("admin/base-data/categories/", views_admin.admin_base_categories, name="admin_base_categories"),
    path("admin/base-data/categories/create/", views_admin.admin_base_category_create, name="admin_base_category_create"),
    path("admin/base-data/categories/<int:category_id>/edit/", views_admin.admin_base_category_edit, name="admin_base_category_edit"),
    path("admin/base-data/categories/<int:category_id>/toggle-active/", views_admin.admin_base_category_toggle_active, name="admin_base_category_toggle_active"),
    path("admin/base-data/categories/<int:category_id>/delete/", views_admin.admin_base_category_delete, name="admin_base_category_delete"),

    path("admin/base-data/items/", views_admin.admin_base_items, name="admin_base_items"),
    path("admin/base-data/items/create/", views_admin.admin_base_item_create, name="admin_base_item_create"),
    path("admin/base-data/items/<int:item_id>/edit/", views_admin.admin_base_item_edit, name="admin_base_item_edit"),
    path("admin/base-data/items/<int:item_id>/delete/", views_admin.admin_base_item_delete, name="admin_base_item_delete"),


    # Admin: Technicians CRUD
    path("admin/technicians/", views_admin.admin_technician_list, name="admin_technicians"),
    path("admin/technicians/create/", views_admin.admin_technician_create, name="admin_technician_create"),
    path("admin/technicians/<int:technician_id>/edit/", views_admin.admin_technician_edit, name="admin_technician_edit"),
    path("admin/technicians/<int:technician_id>/delete/", views_admin.admin_technician_delete, name="admin_technician_delete"),
    path("admin/technicians/<int:technician_id>/toggle-active/", views_admin.admin_technician_toggle_active, name="admin_technician_toggle_active"),
    path("admin/technicians/<int:technician_id>/ledger/", payouts_views.technician_ledger, name="admin_technician_ledger"),

    # Admin: Payment Split Snapshot Report (P4)
    path("admin/payments/split-snapshots/", split_snapshot_views.split_snapshot_list, name="admin_split_snapshots"),
    path("admin/payments/split-snapshots/<int:snapshot_id>/", split_snapshot_views.split_snapshot_detail, name="admin_split_snapshot_detail"),
    path("admin/technicians/<int:technician_id>/ledger/settlement/", payouts_views.technician_settlement, name="admin_technician_settlement"),

    # Admin: Customers — central customer file and history
    path("admin/customers/", views_admin.admin_customer_list, name="admin_customers"),
    path("admin/customers/<int:customer_id>/", views_admin.admin_customer_detail, name="admin_customer_detail"),
    # Admin: Customer lookup API (for order create autofill)
    path("admin/customers/lookup/", views_admin.admin_customer_lookup, name="admin_customer_lookup"),

    # Admin: Orders management
    path("admin/orders/", views_admin.admin_orders, name="admin_orders"),
    path("admin/orders/create/", views_admin.admin_order_create, name="admin_order_create"),
    path("admin/orders/<int:order_id>/", views_admin.admin_order_detail, name="admin_order_detail"),
    path("admin/orders/<int:order_id>/edit/", views_admin.admin_order_edit, name="admin_order_edit"),
    path("admin/orders/<int:order_id>/assign/", views_admin.admin_order_assign, name="admin_order_assign"),

    # Admin: Order cancel request review (Phase 25)
    path("admin/orders/<int:order_id>/cancel-request/approve/", views_admin.admin_cancel_request_approve, name="admin_cancel_request_approve"),
    path("admin/orders/<int:order_id>/cancel-request/reject/", views_admin.admin_cancel_request_reject, name="admin_cancel_request_reject"),

    # Admin: Return to cycle (Phase 14)
    path("admin/orders/<int:order_id>/return-to-cycle/", views_admin.admin_order_return_to_cycle, name="admin_order_return_to_cycle"),

    # Admin: Invoices management
    path("admin/invoices/", views_admin.admin_invoice_list, name="admin_invoices"),
    path("admin/orders/<int:order_id>/invoice/create/", views_admin.admin_invoice_create_from_order, name="admin_invoice_create_from_order"),
    path("admin/invoices/<int:invoice_id>/", views_admin.admin_invoice_detail, name="admin_invoice_detail"),
    path("admin/invoices/<int:invoice_id>/edit/", views_admin.admin_invoice_edit, name="admin_invoice_edit"),
    path("admin/invoices/<str:public_code>/print/", views_admin.admin_invoice_print, name="admin_invoice_print"),

    # Admin: Branding
    path("admin/branding/", views_branding.admin_branding, name="admin_branding"),

    # Admin: Gallery CRUD
    path("admin/gallery/", views_branding.admin_gallery_list, name="admin_gallery"),
    path("admin/gallery/create/", views_branding.admin_gallery_create, name="admin_gallery_create"),
    path("admin/gallery/<int:image_id>/edit/", views_branding.admin_gallery_edit, name="admin_gallery_edit"),
    path("admin/gallery/<int:image_id>/delete/", views_branding.admin_gallery_delete, name="admin_gallery_delete"),

    # Admin: Requests & SMS
    path("admin/requests/", views_admin.admin_request_list, name="admin_requests"),
    path("admin/sms/", include("apps.sms.urls")),

    # Admin: SMS Credit Wallet
    path("admin/sms-credit/", tenant_sms_views.tenant_sms_credit, name="admin_sms_credit"),
    path("admin/sms-credit/recharge/", tenant_sms_views.tenant_sms_recharge, name="admin_sms_recharge"),
    path("admin/sms-credit/transactions/", tenant_sms_views.tenant_sms_transactions, name="admin_sms_transactions"),
    path("admin/sms-credit/invoices/", tenant_sms_views.tenant_sms_invoices, name="admin_sms_invoices"),
    path("admin/sms-credit/invoices/<int:invoice_id>/", tenant_sms_views.tenant_sms_invoice_detail, name="admin_sms_invoice_detail"),

    # Admin: Communication Settings
    path("admin/communication-settings/", tenant_comm_views.tenant_comm_settings, name="admin_communication_settings"),
    path("admin/communication-settings/template/<str:event_key>/", tenant_comm_views.tenant_sms_template_view, name="admin_sms_template_view"),
    path("admin/communication-settings/template/<str:event_key>/request/", tenant_comm_views.tenant_sms_template_change_request, name="admin_sms_template_request"),

    # Admin: Financial Reports (P6)
    path("admin/financial-reports/summary/", financial_report_views.financial_summary, name="financial_summary"),
    path("admin/financial-reports/technicians/", financial_report_views.technician_breakdown, name="financial_technician_breakdown"),
    path("admin/financial-reports/invoices/", financial_report_views.invoice_settlement_detail, name="financial_invoice_settlement"),
    path("admin/financial-reports/cash-control/", financial_report_views.cash_control, name="financial_cash_control"),
    path("admin/financial-reports/platform-fees/", financial_report_views.platform_fee_report, name="financial_platform_fees"),
    path("admin/financial-reports/audit/", financial_report_views.audit_report, name="financial_audit"),

    # Admin: Reports & Notifications
    path("admin/reports/", include("apps.reports.urls")),
    path("admin/notifications/", include("apps.notifications.urls")),

    # =========================================================================
    # TECHNICIAN PANEL (/<company_code>/tech/...)
    # =========================================================================
    path("tech/", include("apps.dashboard.urls_technician")),
    path("tech/orders/", include("apps.orders.urls_technician")),
    path("tech/invoices/", include("apps.invoices.urls_technician")),
    path("tech/notifications/", include("apps.notifications.urls_technician")),

    # =========================================================================
    # PUBLIC / CUSTOMER-FACING MODULES
    # =========================================================================
    # Customer portal (deprecated — redirects to public page)
    # Customer model is kept internally for order/contact data.
    path("customer/", views.redirect_customer_to_public, name="customer_home_redirect"),
    path("invoices/", include("apps.invoices.urls")),
    path("payments/", include("apps.payments.urls")),

    # =========================================================================
    # LEGACY REDIRECTS (Phase 24)
    # These catch old bookmarked/hardcoded URLs and redirect to the correct
    # role-specific panel. No actions are exposed here.
    # =========================================================================
    path("technician/", views.redirect_legacy_technician_home, name="legacy_technician_redirect"),
    path("orders/", legacy_orders_redirect, name="legacy_orders_redirect"),
    path("orders/<path:subpath>", legacy_orders_catch_all, name="legacy_orders_catch_all"),
    path("reports/", legacy_reports_redirect, name="legacy_reports_redirect"),
    path("reports/<path:subpath>", legacy_reports_redirect, name="legacy_reports_catch_all"),
    path("notifications/", legacy_notifications_redirect, name="legacy_notifications_redirect"),
    path("notifications/<path:subpath>", legacy_notifications_redirect, name="legacy_notifications_catch_all"),
]
