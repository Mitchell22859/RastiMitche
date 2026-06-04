"""Company communication provisioning helpers.

This module is intentionally small and idempotent.  It is safe to call when a
company is registered, created by platform owner, or activated.
"""
from __future__ import annotations

from apps.notifications.models import NotificationSetting
from apps.notifications.services import NotificationSettingService
from apps.sms.default_template_texts import get_default_templates
from apps.sms.master_template_defaults import ensure_master_templates
from apps.sms.models import SMSTemplate


def provision_company_communication_defaults(company) -> dict:
    """Ensure the company has all SMS templates and notification settings.

    Returns a dict with counts. Existing customized template text and existing
    NotificationSetting switches are not overwritten/reset.
    """
    if company is None:
        return {"notification_settings": 0, "sms_templates": 0, "new_sms_templates": 0, "repaired_sms_templates": 0}

    ensure_master_templates()
    NotificationSettingService.ensure_defaults(company=company)

    settings_by_key = {
        setting.event_key: setting
        for setting in NotificationSetting.objects.filter(company=company)
    }
    valid_keys = {str(value) for value, _label in SMSTemplate.TemplateKey.choices}

    new_sms = 0
    repaired_sms = 0
    for tpl_data in get_default_templates():
        key = str(tpl_data["event_key"])
        if key not in valid_keys:
            continue

        setting = settings_by_key.get(key)
        is_active = True if setting is None else bool(setting.sms_enabled)

        template, created = SMSTemplate.objects.get_or_create(
            company=company,
            key=key,
            defaults={
                "title": tpl_data["title"],
                "template_text": tpl_data["template_text"],
                "is_active": is_active,
            },
        )
        if created:
            new_sms += 1
            continue

        changed = False
        update_fields = []
        if not template.title:
            template.title = tpl_data["title"]
            update_fields.append("title")
            changed = True
        if not (template.template_text or "").strip():
            template.template_text = tpl_data["template_text"]
            update_fields.append("template_text")
            changed = True
        if changed:
            update_fields.append("updated_at")
            template.save(update_fields=update_fields)
            repaired_sms += 1

    return {
        "notification_settings": NotificationSetting.objects.filter(company=company).count(),
        "sms_templates": SMSTemplate.objects.filter(company=company).count(),
        "new_sms_templates": new_sms,
        "repaired_sms_templates": repaired_sms,
    }
