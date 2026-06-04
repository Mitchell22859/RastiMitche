"""
Platform owner views for reviewing SMS template change requests.
"""
from django.contrib import messages
from django.http import Http404, HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from apps.accounts.permissions import require_platform_owner
from apps.sms.models import SMSTemplate
from apps.sms.models_master import SMSMasterTemplate, SMSTemplateChangeRequest


@require_platform_owner
def request_list(request: HttpRequest) -> HttpResponse:
    """List all SMS template change requests with filtering."""
    status_filter = request.GET.get("status", "")
    qs = SMSTemplateChangeRequest.objects.select_related("company", "created_by", "reviewed_by").order_by("-created_at")
    if status_filter:
        qs = qs.filter(status=status_filter)
    
    pending_count = SMSTemplateChangeRequest.objects.filter(status="pending").count()
    
    return render(request, "platform_core/sms_template_requests/list.html", {
        "requests": qs[:100],
        "status_filter": status_filter,
        "pending_count": pending_count,
        "statuses": SMSTemplateChangeRequest.Status.choices,
    })


@require_platform_owner
def request_detail(request: HttpRequest, request_id: int) -> HttpResponse:
    """Detail view for a single template change request."""
    change_request = get_object_or_404(
        SMSTemplateChangeRequest.objects.select_related("company", "created_by", "reviewed_by"),
        pk=request_id,
    )
    
    # Get current master template for this event
    master_template = SMSMasterTemplate.objects.filter(key=change_request.event_key).first()
    
    # Get current company override
    company_template = SMSTemplate.objects.filter(
        company=change_request.company, key=change_request.event_key
    ).first()
    
    return render(request, "platform_core/sms_template_requests/detail.html", {
        "change_request": change_request,
        "master_template": master_template,
        "company_template": company_template,
    })


@require_platform_owner
def request_approve(request: HttpRequest, request_id: int) -> HttpResponse:
    """Approve a pending template change request with owner-edited final text."""
    if request.method != "POST":
        return redirect("platform_core:owner_sms_template_request_detail", request_id=request_id)
    
    change_request = get_object_or_404(SMSTemplateChangeRequest, pk=request_id)
    
    if change_request.status != SMSTemplateChangeRequest.Status.PENDING:
        messages.warning(request, "\u0627\u06cc\u0646 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0642\u0628\u0644\u0627\u064b \u0628\u0631\u0631\u0633\u06cc \u0634\u062f\u0647 \u0627\u0633\u062a.")
        return redirect("platform_core:owner_sms_template_request_detail", request_id=request_id)
    
    # Owner can edit the final text before approval
    approved_text = request.POST.get("approved_template_text", "").strip()
    admin_response = request.POST.get("admin_response", "").strip()
    
    if not approved_text:
        messages.error(request, "\u0645\u062a\u0646 \u0646\u0647\u0627\u06cc\u06cc \u062a\u0627\u06cc\u06cc\u062f\u0634\u062f\u0647 \u0627\u0644\u0632\u0627\u0645\u06cc \u0627\u0633\u062a.")
        return redirect("platform_core:owner_sms_template_request_detail", request_id=request_id)
    
    # Create or update company-specific SMSTemplate with APPROVED text (NOT requested text)
    company_template, created = SMSTemplate.objects.get_or_create(
        company=change_request.company,
        key=change_request.event_key,
        defaults={
            "title": change_request.event_key,
            "template_text": approved_text,
            "is_active": True,
        },
    )
    if not created:
        company_template.template_text = approved_text
        company_template.is_active = True
        company_template.save(update_fields=["template_text", "is_active", "updated_at"])
    
    # Update the request - preserve requested_template_text, save approved text separately
    change_request.status = SMSTemplateChangeRequest.Status.APPROVED
    change_request.approved_template_text = approved_text
    change_request.reviewed_by = request.user
    change_request.reviewed_at = timezone.now()
    change_request.admin_response = admin_response
    change_request.save(update_fields=[
        "status", "approved_template_text", "reviewed_by", "reviewed_at", "admin_response", "updated_at"
    ])
    
    messages.success(request, f"\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u062a\u0623\u06cc\u06cc\u062f \u0634\u062f \u0648 \u0642\u0627\u0644\u0628 \u0627\u062e\u062a\u0635\u0627\u0635\u06cc \u0634\u0631\u06a9\u062a {change_request.company.name} \u0628\u0647\u200c\u0631\u0648\u0632\u0631\u0633\u0627\u0646\u06cc \u0634\u062f.")
    return redirect("platform_core:owner_sms_template_requests")


@require_platform_owner
def request_reject(request: HttpRequest, request_id: int) -> HttpResponse:
    """Reject a pending template change request."""
    if request.method != "POST":
        return redirect("platform_core:owner_sms_template_request_detail", request_id=request_id)
    
    change_request = get_object_or_404(SMSTemplateChangeRequest, pk=request_id)
    
    if change_request.status != SMSTemplateChangeRequest.Status.PENDING:
        messages.warning(request, "\u0627\u06cc\u0646 \u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0642\u0628\u0644\u0627\u064b \u0628\u0631\u0631\u0633\u06cc \u0634\u062f\u0647 \u0627\u0633\u062a.")
        return redirect("platform_core:owner_sms_template_request_detail", request_id=request_id)
    
    admin_response = request.POST.get("admin_response", "").strip()
    
    change_request.status = SMSTemplateChangeRequest.Status.REJECTED
    change_request.reviewed_by = request.user
    change_request.reviewed_at = timezone.now()
    change_request.admin_response = admin_response or "\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0631\u062f \u0634\u062f."
    change_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "admin_response", "updated_at"])
    
    messages.success(request, "\u062f\u0631\u062e\u0648\u0627\u0633\u062a \u0631\u062f \u0634\u062f.")
    return redirect("platform_core:owner_sms_template_requests")
