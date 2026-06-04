from __future__ import annotations

from django.utils import timezone


def sync_sms_template_from_notification_setting(*, setting) -> int:
    """
    NotificationSetting.sms_enabled is the business-level SMS switch.
    Keep the matching SMSTemplate.is_active aligned with it.
    Uses QuerySet.update() to avoid recursive signal save loops.
    """
    try:
        from apps.sms.models import SMSTemplate
    except Exception:
        return 0

    return SMSTemplate.objects.filter(
        company=setting.company,
        key=setting.event_key,
    ).exclude(
        is_active=setting.sms_enabled,
    ).update(
        is_active=setting.sms_enabled,
        updated_at=timezone.now(),
    )


def sync_notification_setting_from_sms_template(*, template) -> int:
    """
    SMSTemplate.is_active and NotificationSetting.sms_enabled represent the same
    user-facing SMS switch for the same event.
    Uses QuerySet.update() to avoid recursive signal save loops.
    """
    try:
        from apps.notifications.models import NotificationSetting
        from apps.notifications.services import NotificationSettingService
    except Exception:
        return 0

    NotificationSettingService.ensure_defaults(company=template.company)

    return NotificationSetting.objects.filter(
        company=template.company,
        event_key=template.key,
    ).exclude(
        sms_enabled=template.is_active,
    ).update(
        sms_enabled=template.is_active,
        updated_at=timezone.now(),
    )


def sync_company_sms_notification_state(*, company, source: str = "notification") -> int:
    """
    Bulk sync helper.
    source='notification': NotificationSetting.sms_enabled -> SMSTemplate.is_active
    source='template': SMSTemplate.is_active -> NotificationSetting.sms_enabled
    """
    from apps.notifications.models import NotificationSetting
    from apps.notifications.services import NotificationSettingService
    from apps.sms.models import SMSTemplate

    NotificationSettingService.ensure_defaults(company=company)
    changed = 0

    if source == "template":
        templates_by_key = {
            template.key: template
            for template in SMSTemplate.objects.filter(company=company)
        }
        for setting in NotificationSetting.objects.filter(company=company):
            template = templates_by_key.get(setting.event_key)
            if template is None:
                continue
            if setting.sms_enabled != template.is_active:
                setting.sms_enabled = template.is_active
                setting.save(update_fields=["sms_enabled", "updated_at"])
                changed += 1
        return changed

    settings_by_key = {
        setting.event_key: setting
        for setting in NotificationSetting.objects.filter(company=company)
    }
    for template in SMSTemplate.objects.filter(company=company):
        setting = settings_by_key.get(template.key)
        if setting is None:
            continue
        if template.is_active != setting.sms_enabled:
            template.is_active = setting.sms_enabled
            template.save(update_fields=["is_active", "updated_at"])
            changed += 1

    return changed