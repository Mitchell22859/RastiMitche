from django.apps import AppConfig


class SmsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.sms"
    verbose_name = "SMS"

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_ensure_sms_master_templates, sender=self)


def _ensure_sms_master_templates(sender, **kwargs):
    """
    After every migrate run, ensure all SMSMasterTemplate rows exist.
    Idempotent — does not overwrite customized texts, does not send SMS.
    """
    try:
        from apps.sms.master_template_defaults import ensure_master_templates
        ensure_master_templates()
    except Exception:
        # Never break migrate if this fails (e.g. table not yet created on first run).
        pass
