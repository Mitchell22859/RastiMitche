"""
Accounts - Selectors.

Read operations for accounts, always scoped by company.
"""
from typing import Optional

from django.db.models import QuerySet

from .models import CompanyUser, Customer, Technician, TechnicianCategorySkill


class CompanyUserSelector:
    """Read operations for CompanyUser."""

    @staticmethod
    def get_users_for_company(*, company) -> QuerySet[CompanyUser]:
        return CompanyUser.objects.filter(company=company)

    @staticmethod
    def get_by_phone(*, phone: str) -> Optional[CompanyUser]:
        return CompanyUser.objects.filter(phone=phone).first()

    @staticmethod
    def get_by_id_for_company(*, user_id: int, company) -> Optional[CompanyUser]:
        return CompanyUser.objects.filter(id=user_id, company=company).first()


class TechnicianSelector:
    """Read operations for Technicians."""

    @staticmethod
    def get_for_company(*, company) -> QuerySet[Technician]:
        return Technician.objects.filter(company=company)

    @staticmethod
    def get_available(*, company) -> QuerySet[Technician]:
        return Technician.objects.filter(company=company, is_available=True)


class CustomerSelector:
    """Read operations for Customers."""

    @staticmethod
    def get_for_company(*, company) -> QuerySet[Customer]:
        return Customer.objects.filter(company=company)

    @staticmethod
    def get_by_phone(*, company, phone: str) -> Optional[Customer]:
        return Customer.objects.filter(company=company, phone=phone).first()



class TechnicianCategorySkillSelector:
    """Read operations for TechnicianCategorySkill."""

    @staticmethod
    def get_for_technician(*, technician: Technician) -> QuerySet[TechnicianCategorySkill]:
        """Get all category skills for a technician."""
        return TechnicianCategorySkill.objects.filter(technician=technician)

    @staticmethod
    def get_for_company(*, company) -> QuerySet[TechnicianCategorySkill]:
        """Get all category skills for technicians in a company."""
        return TechnicianCategorySkill.objects.filter(
            technician__company=company,
        )

    @staticmethod
    def get_by_category(*, technician: Technician, category) -> Optional[TechnicianCategorySkill]:
        """Get a technician's skill for a specific category."""
        return TechnicianCategorySkill.objects.filter(
            technician=technician, category=category,
        ).first()
