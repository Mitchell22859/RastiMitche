from django.contrib import admin

from .models import Report


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "report_type", "generated_at"]
    list_filter = ["report_type", "company"]
