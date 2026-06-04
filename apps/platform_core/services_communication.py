"""
Communication Template Resolution Service.

DEPRECATED — This service is legacy code from a previous design iteration.

The CommunicationTemplate system is NOT connected to the active SMS/notification
dispatch pipeline. This service is only called by views_comm_templates.py (the
platform owner CommunicationTemplate UI) which itself is deprecated and hidden
from navigation.

Active system (used for real SMS/notification dispatch):
    - apps.notifications.services_events.NotificationEventService
    - apps.notifications.dispatchers.NotificationDispatcher
    - apps.sms.services.SMSQueueFromTemplateService
    - apps.platform_core.services_platform_sms.PlatformSMSQueueService

Do NOT use CommunicationTemplateService for new SMS/event work.
"""
import re
from typing import Optional

from django.db import models

from apps.tenants.models import Company
from .models import CommunicationTemplate, CommunicationTemplateCompanySetting

ALLOWED_PLACEHOLDERS = {
    "company_name", "company_code", "operator_name", "technician_name",
    "order_id", "order_status", "invoice_id", "invoice_amount",
    "payment_status", "sms_balance", "sms_remaining_count", "tracking_code",
    "customer_name", "customer_phone", "customer_address",
}

PLACEHOLDER_RE = re.compile(r"\{\{\s*(\w+)\s*\}\}")
UNSAFE_URL_RE = re.compile(r"^(https?://|javascript:|//)", re.IGNORECASE)


class CommunicationTemplateService:
    @staticmethod
    def validate_placeholders(text: str) -> tuple[bool, list[str]]:
        found = set(PLACEHOLDER_RE.findall(text))
        invalid = found - ALLOWED_PLACEHOLDERS
        return len(invalid) == 0, list(invalid)

    @staticmethod
    def validate_action_url(url: str) -> bool:
        if not url:
            return True
        return not bool(UNSAFE_URL_RE.match(url.strip()))

    @staticmethod
    def is_enabled_for_company(template: CommunicationTemplate, company: Company) -> bool:
        if not template.is_active:
            return False
        if template.is_required:
            return True
        if not template.allow_company_toggle:
            return True
        setting = CommunicationTemplateCompanySetting.objects.filter(
            company=company, template=template
        ).first()
        if setting is None:
            return True
        return setting.is_enabled

    @staticmethod
    def get_template(company: Company, event_key: str, channel: str, recipient_type: str) -> Optional[CommunicationTemplate]:
        # 1. Company-specific active template
        tpl = CommunicationTemplate.objects.filter(
            company=company, event_key=event_key, channel=channel,
            recipient_type=recipient_type, is_active=True,
        ).first()
        if tpl and CommunicationTemplateService.is_enabled_for_company(tpl, company):
            return tpl
        # 2. Global active template
        tpl = CommunicationTemplate.objects.filter(
            company__isnull=True, event_key=event_key, channel=channel,
            recipient_type=recipient_type, is_active=True,
        ).first()
        if tpl and CommunicationTemplateService.is_enabled_for_company(tpl, company):
            return tpl
        return None

    @staticmethod
    def render_template(template: CommunicationTemplate, context: dict) -> dict:
        title = template.title_template
        body = template.body_template
        action_url = template.action_url_template
        for key, value in context.items():
            placeholder = "{{ " + key + " }}"
            title = title.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
            action_url = action_url.replace(placeholder, str(value))
        return {"title": title, "body": body, "action_label": template.action_label, "action_url": action_url}

    @staticmethod
    def get_all_for_company(company: Company) -> list[dict]:
        templates = CommunicationTemplate.objects.filter(
            is_active=True, allow_company_toggle=True
        ).filter(models.Q(company__isnull=True) | models.Q(company=company))
        result = []
        for tpl in templates:
            setting = CommunicationTemplateCompanySetting.objects.filter(company=company, template=tpl).first()
            result.append({
                "template": tpl,
                "is_enabled": setting.is_enabled if setting else True,
                "is_required": tpl.is_required,
                "can_toggle": tpl.allow_company_toggle and not tpl.is_required,
            })
        return result
