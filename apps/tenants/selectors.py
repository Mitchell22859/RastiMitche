"""
Tenants - Selectors.

Read operations for tenant-related queries (public page, services, gallery).
"""
from typing import Optional

from django.db.models import QuerySet

from .models import (
    Company,
    CompanyGalleryImage,
    CompanyPage,
    CompanyService,
    CompanyServiceCategory,
    CompanyServiceSubCategory,
    CompanySettings,
    ServiceRequest,
)


class CompanySelector:
    """Read operations for Company model."""

    @staticmethod
    def get_by_code(*, code: str) -> Optional[Company]:
        return Company.objects.filter(code=code, is_active=True).first()

    @staticmethod
    def get_all_active() -> QuerySet[Company]:
        return Company.objects.filter(is_active=True)

    @staticmethod
    def get_by_id(*, company_id: int) -> Optional[Company]:
        return Company.objects.filter(id=company_id).first()


class CompanyPageSelector:
    """Read operations for CompanyPage."""

    @staticmethod
    def get_for_company(*, company) -> Optional[CompanyPage]:
        """Get the public page for a company (creates if not exists)."""
        page, _ = CompanyPage.objects.get_or_create(company=company)
        return page


class CompanyServiceSelector:
    """Read operations for CompanyService."""

    @staticmethod
    def get_active_for_company(*, company) -> QuerySet[CompanyService]:
        """Get active services for a company (shown on public page)."""
        return CompanyService.objects.filter(company=company, is_active=True)

    @staticmethod
    def get_all_for_company(*, company) -> QuerySet[CompanyService]:
        """Get all services for a company (admin view)."""
        return CompanyService.objects.filter(company=company)

    @staticmethod
    def get_by_id_for_company(*, service_id: int, company) -> Optional[CompanyService]:
        return CompanyService.objects.filter(id=service_id, company=company).first()


class CompanyGallerySelector:
    """Read operations for CompanyGalleryImage."""

    @staticmethod
    def get_active_for_company(*, company) -> QuerySet[CompanyGalleryImage]:
        """Get active gallery images for public display."""
        return CompanyGalleryImage.objects.filter(company=company, is_active=True)

    @staticmethod
    def get_all_for_company(*, company) -> QuerySet[CompanyGalleryImage]:
        """Get all gallery images (admin view)."""
        return CompanyGalleryImage.objects.filter(company=company)


class ServiceRequestSelector:
    """Read operations for ServiceRequest."""

    @staticmethod
    def get_for_company(*, company) -> QuerySet[ServiceRequest]:
        """Get all service requests for a company (admin view)."""
        return ServiceRequest.objects.filter(company=company)

    @staticmethod
    def get_by_id_for_company(*, request_id: int, company) -> Optional[ServiceRequest]:
        return ServiceRequest.objects.filter(id=request_id, company=company).first()



class CompanyServiceCategorySelector:
    """Read operations for CompanyServiceCategory."""

    @staticmethod
    def get_active_for_company(*, company) -> QuerySet[CompanyServiceCategory]:
        """Get active categories for a company."""
        return CompanyServiceCategory.objects.filter(company=company, is_active=True)

    @staticmethod
    def get_all_for_company(*, company) -> QuerySet[CompanyServiceCategory]:
        """Get all categories (admin view)."""
        return CompanyServiceCategory.objects.filter(company=company)

    @staticmethod
    def get_by_id_for_company(*, category_id: int, company) -> Optional[CompanyServiceCategory]:
        return CompanyServiceCategory.objects.filter(id=category_id, company=company).first()


class CompanyServiceSubCategorySelector:
    """Read operations for CompanyServiceSubCategory."""

    @staticmethod
    def get_active_for_category(*, category: CompanyServiceCategory) -> QuerySet[CompanyServiceSubCategory]:
        """Get active subcategories for a specific category."""
        return CompanyServiceSubCategory.objects.filter(category=category, is_active=True)

    @staticmethod
    def get_active_for_company(*, company) -> QuerySet[CompanyServiceSubCategory]:
        """Get all active subcategories for a company."""
        return CompanyServiceSubCategory.objects.filter(company=company, is_active=True)

    @staticmethod
    def get_by_id_for_company(*, subcategory_id: int, company) -> Optional[CompanyServiceSubCategory]:
        return CompanyServiceSubCategory.objects.filter(id=subcategory_id, company=company).first()

    @staticmethod
    def get_for_category_json(*, company) -> list[dict]:
        """
        Get all subcategories grouped by category for JSON (used in dynamic dropdown JS).
        Returns list of {id, title, category_id, base_price} dicts.
        """
        subcats = CompanyServiceSubCategory.objects.filter(
            company=company, is_active=True
        ).values("id", "title", "category_id", "base_price")
        # Convert Decimal to int for JSON serialization
        return [
            {
                "id": s["id"],
                "title": s["title"],
                "category_id": s["category_id"],
                "base_price": int(s["base_price"]) if s["base_price"] else 0,
            }
            for s in subcats
        ]



def get_company_settings(company: Company) -> CompanySettings:
    """
    Get or create CompanySettings for a company.

    Always returns a valid CompanySettings instance.
    If none exists, creates one with default values.
    """
    settings, _ = CompanySettings.objects.get_or_create(company=company)
    return settings
