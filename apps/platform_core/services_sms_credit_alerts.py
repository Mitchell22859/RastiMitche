"""SMS credit alert service.

Company SMS credit alerts are platform-paid messages.
They must create NotificationEvent records and PlatformSMSOutbox rows, and must
never debit the tenant company's SMS wallet.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from django.conf import settings
from django.utils import timezone

from apps.notifications.event_catalog import EventKey
from apps.notifications.models import NotificationEvent
from apps.notifications.services_events import NotificationEventService
from apps.platform_core.models import CompanySMSWallet
from apps.tenants.models import Company


@dataclass
class SMSCreditAlertResult:
    company_id: int
    company_code: str
    balance_rial: int
    threshold_rial: int
    status: str
    event_key: str = ""
    dedup_key: str = ""
    event_id: Optional[int] = None
    message: str = ""


class SMSCreditAlertService:
    """Checks tenant SMS wallets and queues platform-paid alerts for admins."""

    @staticmethod
    def default_low_threshold_rial() -> int:
        return int(getattr(settings, "SMS_CREDIT_LOW_THRESHOLD_RIAL", 100000) or 100000)

    @staticmethod
    def _company_name(company: Company) -> str:
        return (
            getattr(company, "name", "")
            or getattr(company, "title", "")
            or getattr(company, "display_name", "")
            or getattr(company, "code", "")
            or "شرکت"
        )

    @staticmethod
    def _get_wallet_balance(company: Company) -> int:
        wallet = CompanySMSWallet.objects.filter(company=company).first()
        if wallet is None:
            return 0
        return int(getattr(wallet, "balance_rial", 0) or 0)

    @staticmethod
    def check_company(
        *,
        company: Company,
        threshold_rial: int | None = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> SMSCreditAlertResult:
        threshold = int(threshold_rial if threshold_rial is not None else SMSCreditAlertService.default_low_threshold_rial())
        balance = SMSCreditAlertService._get_wallet_balance(company)

        if balance <= 0:
            event_key = EventKey.SMS_CREDIT_EMPTY_ADMIN
            status = "empty"
        elif balance <= threshold:
            event_key = EventKey.SMS_CREDIT_LOW_ADMIN
            status = "low"
        else:
            return SMSCreditAlertResult(
                company_id=company.id,
                company_code=getattr(company, "code", ""),
                balance_rial=balance,
                threshold_rial=threshold,
                status="ok",
                message="اعتبار پیامک کافی است.",
            )

        today = timezone.localdate().isoformat()
        dedup_key = f"{event_key}:company:{company.id}:{today}"

        if not force and NotificationEvent.objects.filter(dedup_key=dedup_key).exists():
            return SMSCreditAlertResult(
                company_id=company.id,
                company_code=getattr(company, "code", ""),
                balance_rial=balance,
                threshold_rial=threshold,
                status="already_queued_today",
                event_key=event_key,
                dedup_key=dedup_key,
                message="این هشدار امروز قبلاً ثبت شده است.",
            )

        if dry_run:
            return SMSCreditAlertResult(
                company_id=company.id,
                company_code=getattr(company, "code", ""),
                balance_rial=balance,
                threshold_rial=threshold,
                status=f"would_queue_{status}",
                event_key=event_key,
                dedup_key=dedup_key,
                message="Dry run: پیام واقعی وارد صف نشد.",
            )

        event = NotificationEventService.emit(
            event_key=event_key,
            company=company,
            payload={
                "company_name": SMSCreditAlertService._company_name(company),
                "company_code": getattr(company, "code", ""),
                "sms_balance_rial": balance,
                "sms_low_threshold_rial": threshold,
            },
            dedup_key=dedup_key,
            use_on_commit=False,
        )

        return SMSCreditAlertResult(
            company_id=company.id,
            company_code=getattr(company, "code", ""),
            balance_rial=balance,
            threshold_rial=threshold,
            status="queued",
            event_key=event_key,
            dedup_key=dedup_key,
            event_id=event.id if event else None,
            message="هشدار اعتبار پیامک وارد رویداد مرکزی شد.",
        )

    @staticmethod
    def check_all(
        *,
        company_code: str = "",
        threshold_rial: int | None = None,
        dry_run: bool = False,
        force: bool = False,
    ) -> list[SMSCreditAlertResult]:
        companies = Company.objects.all().order_by("id")
        if company_code:
            companies = companies.filter(code=company_code)

        return [
            SMSCreditAlertService.check_company(
                company=company,
                threshold_rial=threshold_rial,
                dry_run=dry_run,
                force=force,
            )
            for company in companies
        ]
