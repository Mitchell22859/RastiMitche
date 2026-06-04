"""
SMS Master Template Defaults.

Idempotent initializer for platform master SMS templates.
The default texts come from apps.sms.default_template_texts so the platform
master templates and company templates share one central source of text.
"""
from .default_template_texts import get_default_templates
from .models_master import SMSMasterTemplate


_SCOPE_MAP = {
    "company": SMSMasterTemplate.Scope.COMPANY,
    "platform": SMSMasterTemplate.Scope.PLATFORM,
}

_RECIPIENT_MAP = {
    "customer": SMSMasterTemplate.RecipientType.CUSTOMER,
    "technician": SMSMasterTemplate.RecipientType.TECHNICIAN,
    "admin": SMSMasterTemplate.RecipientType.ADMIN,
    "operator": SMSMasterTemplate.RecipientType.ADMIN,
    "platform_admin": SMSMasterTemplate.RecipientType.PLATFORM_ADMIN,
}


def ensure_master_templates() -> dict:
    """
    Idempotently create/repair SMSMasterTemplate rows for all SMS-supported events.

    Existing platform-customized template_text is not overwritten.
    """
    all_definitions = get_default_templates()
    created_count = 0
    updated_count = 0

    for defn in all_definitions:
        variables = defn.get("template_variables") or []
        obj, created = SMSMasterTemplate.objects.get_or_create(
            key=defn["event_key"],
            defaults={
                "scope": _SCOPE_MAP.get(defn.get("scope"), SMSMasterTemplate.Scope.COMPANY),
                "recipient_type": _RECIPIENT_MAP.get(defn.get("recipient_type"), SMSMasterTemplate.RecipientType.CUSTOMER),
                "title": defn["title"],
                "template_text": defn["template_text"],
                "allowed_variables": ",".join(variables),
                "is_active": True,
            },
        )

        if created:
            created_count += 1
            continue

        changed = False
        update_fields = []
        if not obj.title:
            obj.title = defn["title"]
            update_fields.append("title")
            changed = True
        if not obj.allowed_variables and variables:
            obj.allowed_variables = ",".join(variables)
            update_fields.append("allowed_variables")
            changed = True
        if not (obj.template_text or "").strip():
            obj.template_text = defn["template_text"]
            update_fields.append("template_text")
            changed = True
        if changed:
            update_fields.append("updated_at")
            obj.save(update_fields=update_fields)
            updated_count += 1

    return {
        "created": created_count,
        "updated": updated_count,
        "total": len(all_definitions),
    }
