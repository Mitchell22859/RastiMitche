"""
Invoices - Short Public Invoice URL.

Served at /i/<public_code>/

This provides a globally-accessible short link to view a public invoice.
No authentication required. No tenant resolution needed because
Invoice.public_code has a unique=True constraint at the database level.

Safety notes:
- public_code is globally unique (enforced by DB constraint + model logic).
- Cancelled invoices are hidden (404).
- Draft invoices are hidden (404) — only ISSUED and PAID are shown.
- The view does NOT require request.company since it resolves globally.
"""
from django.urls import path

from .views_public_short import short_public_invoice_detail

urlpatterns = [
    path("", short_public_invoice_detail, name="invoice_short_public"),
]
