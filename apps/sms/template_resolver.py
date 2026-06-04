"""
SMS Template Resolver.

Centralized resolution of effective SMS template for both display and sending.

Resolution order:
1. Approved company override (SMSTemplate backed by approved SMSTemplateChangeRequest)
2. Platform master template (SMSMasterTemplate)
3. None (no effective template)
"""
from typing import Optional

from .models import SMSTemplate
from .models_master import SMSMasterTemplate, SMSTemplateChangeRequest


def resolve_effective_sms_template(*, company, event_key: str) -> Optional[dict]:
    """
    Resolve the effective SMS template for a company/event.

    Returns dict with:
        - text: template text
        - source: 'approved_override' | 'master' | None
        - source_label: Persian label
        - template_obj: the template model instance (SMSTemplate or SMSMasterTemplate)
        - allowed_variables: comma-separated variables string

    Or None if no effective template exists.
    """
    # 1. Check for approved override
    has_approved = SMSTemplateChangeRequest.objects.filter(
        company=company, event_key=event_key, status="approved"
    ).exists()

    if has_approved:
        company_template = SMSTemplate.objects.filter(company=company, key=event_key).first()
        if company_template and company_template.template_text:
            return {
                "text": company_template.template_text,
                "source": "approved_override",
                "source_label": "\u0642\u0627\u0644\u0628 \u0627\u062e\u062a\u0635\u0627\u0635\u06cc \u062a\u0627\u06cc\u06cc\u062f\u0634\u062f\u0647 \u0634\u0631\u06a9\u062a",
                "template_obj": company_template,
                "allowed_variables": "",
                "is_active": company_template.is_active,
                "send_start_time": company_template.send_start_time,
                "send_end_time": company_template.send_end_time,
            }

    # 2. Fallback to master template
    master = SMSMasterTemplate.objects.filter(key=event_key, is_active=True).first()
    if master:
        return {
            "text": master.template_text,
            "source": "master",
            "source_label": "\u0642\u0627\u0644\u0628 \u0627\u0635\u0644\u06cc \u067e\u0644\u062a\u0641\u0631\u0645",
            "template_obj": master,
            "allowed_variables": master.allowed_variables,
            "is_active": True,
            "send_start_time": None,
            "send_end_time": None,
        }

    # 3. No effective template
    return None
