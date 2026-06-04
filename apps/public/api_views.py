"""
Public API - Live availability check endpoints.
No authentication required. Returns only generic availability status.
"""
import re
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from apps.accounts.models import CompanyUser
from apps.tenants.models import Company

RESERVED_SLUGS = {
    "login", "logout", "register", "owner-platform", "admin", "api",
    "static", "media", "pricing", "features", "about", "contact",
    "health", "dashboard", "tech", "customer", "payments", "invoices",
    "request", "favicon", "loginlogin",
}

USERNAME_REGEX = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
COMPANY_CODE_REGEX = re.compile(r"^[a-z0-9][a-z0-9-]*$")


@require_GET
def check_username(request):
    value = (request.GET.get("value") or "").strip().lower()
    if not value:
        return JsonResponse({"available": False, "message": ""})
    if len(value) < 3:
        return JsonResponse({"available": False, "message": "\u062d\u062f\u0627\u0642\u0644 \u06f3 \u06a9\u0627\u0631\u0627\u06a9\u062a\u0631"})
    if len(value) > 50:
        return JsonResponse({"available": False, "message": "\u062d\u062f\u0627\u06a9\u062b\u0631 \u06f5\u06f0 \u06a9\u0627\u0631\u0627\u06a9\u062a\u0631"})
    if not USERNAME_REGEX.match(value):
        return JsonResponse({"available": False, "message": "\u0641\u0631\u0645\u062a \u0645\u0639\u062a\u0628\u0631 \u0646\u06cc\u0633\u062a (\u062d\u0631\u0648\u0641 \u0627\u0646\u06af\u0644\u06cc\u0633\u06cc\u060c \u0627\u0639\u062f\u0627\u062f\u060c _ \u0648 -)"})
    if value in RESERVED_SLUGS:
        return JsonResponse({"available": False, "message": "\u0627\u06cc\u0646 \u0646\u0627\u0645 \u0631\u0632\u0631\u0648 \u0634\u062f\u0647 \u0627\u0633\u062a"})
    if CompanyUser.objects.filter(username=value).exists():
        return JsonResponse({"available": False, "message": "\u0642\u0628\u0644\u0627\u064b \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u0634\u062f\u0647 \u0627\u0633\u062a"})
    return JsonResponse({"available": True, "message": "\u0642\u0627\u0628\u0644 \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u0627\u0633\u062a"})


@require_GET
def check_company_code(request):
    value = (request.GET.get("value") or "").strip().lower()
    if not value:
        return JsonResponse({"available": False, "message": ""})
    if len(value) < 3:
        return JsonResponse({"available": False, "message": "\u062d\u062f\u0627\u0642\u0644 \u06f3 \u06a9\u0627\u0631\u0627\u06a9\u062a\u0631"})
    if len(value) > 50:
        return JsonResponse({"available": False, "message": "\u062d\u062f\u0627\u06a9\u062b\u0631 \u06f5\u06f0 \u06a9\u0627\u0631\u0627\u06a9\u062a\u0631"})
    if not COMPANY_CODE_REGEX.match(value):
        return JsonResponse({"available": False, "message": "\u0641\u0631\u0645\u062a \u0645\u0639\u062a\u0628\u0631 \u0646\u06cc\u0633\u062a (\u062d\u0631\u0648\u0641 \u0627\u0646\u06af\u0644\u06cc\u0633\u06cc\u060c \u0627\u0639\u062f\u0627\u062f \u0648 -)"})
    if value in RESERVED_SLUGS:
        return JsonResponse({"available": False, "message": "\u0627\u06cc\u0646 \u06a9\u062f \u0631\u0632\u0631\u0648 \u0634\u062f\u0647 \u0627\u0633\u062a"})
    if Company.objects.filter(code=value).exists():
        return JsonResponse({"available": False, "message": "\u0642\u0628\u0644\u0627\u064b \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u0634\u062f\u0647 \u0627\u0633\u062a"})
    return JsonResponse({"available": True, "message": "\u0642\u0627\u0628\u0644 \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u0627\u0633\u062a"})


@require_GET
def check_admin_email(request):
    """Check admin email format only. Email is NOT required to be unique
    because the same person may have multiple accounts."""
    value = (request.GET.get("value") or "").strip().lower()
    if not value:
        return JsonResponse({"available": False, "message": ""})
    if "@" not in value or "." not in value.split("@")[-1]:
        return JsonResponse({"available": False, "message": "\u0641\u0631\u0645\u062a \u0627\u06cc\u0645\u06cc\u0644 \u0645\u0639\u062a\u0628\u0631 \u0646\u06cc\u0633\u062a"})
    return JsonResponse({"available": True, "message": "\u0642\u0627\u0628\u0644 \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u0627\u0633\u062a"})


@require_GET
def check_company_email(request):
    value = (request.GET.get("value") or "").strip().lower()
    if not value:
        return JsonResponse({"available": False, "message": ""})
    if "@" not in value or "." not in value.split("@")[-1]:
        return JsonResponse({"available": False, "message": "\u0641\u0631\u0645\u062a \u0627\u06cc\u0645\u06cc\u0644 \u0645\u0639\u062a\u0628\u0631 \u0646\u06cc\u0633\u062a"})
    if Company.objects.filter(email=value).exists():
        return JsonResponse({"available": False, "message": "\u0642\u0628\u0644\u0627\u064b \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u0634\u062f\u0647 \u0627\u0633\u062a"})
    return JsonResponse({"available": True, "message": "\u0642\u0627\u0628\u0644 \u0627\u0633\u062a\u0641\u0627\u062f\u0647 \u0627\u0633\u062a"})
