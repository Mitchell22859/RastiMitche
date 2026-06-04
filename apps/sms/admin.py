from django.contrib import admin

from .models import SMSOutbox, SMSProvider, SMSTemplate


@admin.register(SMSProvider)
class SMSProviderAdmin(admin.ModelAdmin):
    list_display = ["name", "company", "provider_type", "is_active"]
    list_filter = ["provider_type", "is_active", "company"]
    search_fields = ["name", "company__name", "company__code"]


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = ["title", "company", "key", "is_active"]
    list_filter = ["key", "is_active", "company"]
    search_fields = ["title", "template_text", "company__name", "company__code"]


@admin.register(SMSOutbox)
class SMSOutboxAdmin(admin.ModelAdmin):
    list_display = ["id", "company", "phone_number", "status", "template_key", "attempt_count", "sent_at", "delivered_at", "created_at"]
    list_filter = ["status", "template_key", "company"]
    search_fields = ["phone_number", "message", "provider_message_id", "company__name", "company__code"]
    readonly_fields = ["created_at", "updated_at", "queued_at", "sending_at", "sent_at", "delivered_at", "failed_at", "last_attempt_at"]
