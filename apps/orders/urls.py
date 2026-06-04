"""
Orders - Public/Customer URL configuration (Phase 24 cleanup).

This URL conf is NO LONGER included in the tenant URL routing.
It previously exposed technician-style actions (accept, complete, cancel,
status_update) at the public /<company_code>/orders/ level.

As of Phase 24, all order actions are served exclusively through:
- /<company_code>/admin/orders/...  → admin/operator panel
- /<company_code>/tech/orders/...   → technician panel

This file is retained for backward compatibility with any reverse() calls
or tests that reference the 'orders' app_name, but it contains NO action
routes. The legacy /<company_code>/orders/ path is handled by redirect views
in apps.tenants.views_redirects.
"""
from django.urls import path

app_name = "orders"

# No public order action routes. All actions live under /admin/ or /tech/.
urlpatterns = []
