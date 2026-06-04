from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.notifications"
    verbose_name = "Notifications"
    def ready(self):
        try:
            import apps.notifications.signals  # noqa: F401
        except Exception:
            pass
        from apps.notifications import signals
        signals.connect_sms_template_signal()