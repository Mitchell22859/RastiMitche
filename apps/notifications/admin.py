from django.contrib import admin

from .models import Notification, NotificationSetting


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "recipient", "notification_type", "is_read"]
    list_filter = ["notification_type", "is_read", "company"]



@admin.register(NotificationSetting)
class NotificationSettingAdmin(admin.ModelAdmin):
    list_display = ["company", "event_key", "in_app_enabled", "sms_enabled"]
    list_filter = ["event_key", "in_app_enabled", "sms_enabled", "company"]


from .models import NotificationEvent

@admin.register(NotificationEvent)
class NotificationEventAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "event_key", "status", "target_model", "target_id", "created_at", "dispatched_at"]
    list_filter = ["status", "event_key", "company"]
    search_fields = ["event_key", "dedup_key", "result_message"]
    readonly_fields = ["created_at", "updated_at", "dispatched_at"]

