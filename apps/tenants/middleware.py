"""
Tenants - Middleware.

This is the CORE of the path-based multi-tenancy system.

How it works:
1. Incoming request URL is inspected.
2. If the URL matches a tenant-exempt prefix (e.g., /loginlogin/, /static/), skip.
3. Otherwise, extract the first path segment as the company code.
4. Look up the Company with that code.
5. If not found or inactive → 404.
6. Attach request.company for downstream use.

IMPORTANT: Every tenant-scoped view MUST use request.company to filter data.
"""
import logging
from typing import Callable

from django.conf import settings
from django.http import Http404, HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class TenantMiddleware:
    """
    Path-based tenant resolution middleware.

    Resolves tenant from the first URL path segment.
    Attaches `request.company` to all tenant-scoped requests.
    """

    def __init__(self, get_response: Callable[[HttpRequest], HttpResponse]) -> None:
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        # Default: no company attached
        request.company = None  # type: ignore[attr-defined]
        request.is_tenant_request = False  # type: ignore[attr-defined]

        path = request.path.strip("/")
        path_segments = path.split("/") if path else []

        # If path is empty or starts with an exempt prefix, skip tenant resolution
        if not path_segments or self._is_exempt(path_segments[0]):
            return self.get_response(request)

        # Determine the company code segment
        # For /api/<company_code>/... the company code is the SECOND segment
        # For /<company_code>/... the company code is the FIRST segment
        if path_segments[0] == "api" and len(path_segments) >= 2:
            # API route: /api/<company_code>/...
            # Skip if it's a platform API route
            if path_segments[1] == "platform":
                return self.get_response(request)
            company_code = path_segments[1]
        else:
            # Regular tenant route: /<company_code>/...
            company_code = path_segments[0]

        # Resolve the company
        company = self._resolve_company(company_code)

        if company is None:
            logger.warning(f"Tenant not found: {company_code}")
            raise Http404("Company not found.")

        if not company.is_active:
            logger.warning(f"Inactive tenant accessed: {company_code}")
            raise Http404("Company not found.")

        # Attach company to request — this is used everywhere downstream
        request.company = company  # type: ignore[attr-defined]
        request.is_tenant_request = True  # type: ignore[attr-defined]

        return self.get_response(request)

    def _is_exempt(self, first_segment: str) -> bool:
        """Check if the path should bypass tenant resolution."""
        exempt_prefixes = getattr(settings, "TENANT_EXEMPT_PREFIXES", [])
        return first_segment in exempt_prefixes

    def _resolve_company(self, code: str):
        """
        Look up company by code.
        Returns Company instance or None.
        """
        from .models import Company

        try:
            return Company.objects.get(code=code)
        except Company.DoesNotExist:
            return None
