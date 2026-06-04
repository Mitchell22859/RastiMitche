"""
Technician notification URLs.

Served under /<company_code>/tech/notifications/.
"""
from django.urls import path

from . import views

app_name = "notifications_technician"

urlpatterns = [
    path("", views.notification_list, name="list"),
    path("<int:notification_id>/read/", views.notification_mark_read, name="mark_read"),
]
