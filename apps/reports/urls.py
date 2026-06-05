"""Reports - URLs. Served under /<company_code>/reports/"""
from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_list, name="list"),
    path("customer-segments/", views.customer_segment_report, name="customer_segments"),
    path("discount-campaigns/", views.discount_campaign_list, name="discount_campaign_list"),
    path("discount-campaigns/new/", views.discount_campaign_create_from_segment, name="discount_campaign_new"),
    path("discount-campaigns/manual/", views.discount_campaign_create_manual, name="discount_campaign_manual"),
    path("discount-campaigns/customer/<int:customer_id>/new/", views.discount_campaign_single_customer, name="discount_campaign_single_customer"),
    path("discount-campaigns/<int:campaign_id>/", views.discount_campaign_detail, name="discount_campaign_detail"),
]
