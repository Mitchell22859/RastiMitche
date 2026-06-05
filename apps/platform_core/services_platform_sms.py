"""Platform-paid SMS service layer."""
from __future__ import annotations

import re
from typing import Optional

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.sms.providers import get_sms_provider
from apps.sms.providers.base import SMSSendRequest

from .models import PlatformSMSMessageTypeSetting, PlatformSMSOutbox, PlatformSMSProviderSetting


_IRAN_MOBILE_REGEX = re.compile(r"^09[0-9]{9}$")


def normalize_platform_sms_phone(raw: str) -> Optional[str]:
    if not raw:
        return None
    phone = re.sub(r"[\s\-\(\)]+", "", raw.strip())
    phone = (
        phone
        .replace("۰", "0").replace("۱", "1").replace("۲", "2").replace("۳", "3").replace("۴", "4")
        .replace("۵", "5").replace("۶", "6").replace("۷", "7").replace("۸", "8").replace("۹", "9")
        .replace("٠", "0").replace("١", "1").replace("٢", "2").replace("٣", "3").replace("٤", "4")
        .replace("٥", "5").replace("٦", "6").replace("٧", "7").replace("٨", "8").replace("٩", "9")
    )
    if phone.startswith("+"):
        phone = phone[1:]
    if phone.startswith("0098"):
        phone = "0" + phone[4:]
    elif phone.startswith("98") and len(phone) == 12:
        phone = "0" + phone[2:]
    elif phone.startswith("9") and len(phone) == 10:
        phone = "0" + phone
    return phone if _IRAN_MOBILE_REGEX.match(phone) else None


class PlatformSMSMessageTypeService:
    @staticmethod
    def default_rows() -> list[dict]:
        Payer = PlatformSMSMessageTypeSetting.Payer
        Key = PlatformSMSMessageTypeSetting.MessageKey
        return [
            {"key": Key.ORDER_CREATED_ADMIN, "title": "سفارش جدید - مدیر شرکت", "payer": Payer.COMPANY, "default_company_sms_enabled": False},
            {"key": Key.ORDER_AVAILABLE_TECHNICIAN, "title": "سفارش جدید - تکنسین‌ها", "payer": Payer.COMPANY, "default_company_sms_enabled": False},
            {"key": Key.ORDER_ASSIGNED_TECHNICIAN, "title": "تخصیص سفارش - تکنسین", "payer": Payer.COMPANY, "default_company_sms_enabled": True},
            {"key": Key.ORDER_ACCEPTED_CUSTOMER, "title": "پذیرش سفارش - مشتری", "payer": Payer.COMPANY, "default_company_sms_enabled": True},
            {"key": Key.ORDER_COMPLETED_CUSTOMER, "title": "اتمام سفارش - مشتری", "payer": Payer.COMPANY, "default_company_sms_enabled": True},
            {"key": Key.ORDER_CANCEL_REQUESTED_ADMIN, "title": "درخواست لغو - مدیر شرکت", "payer": Payer.COMPANY, "default_company_sms_enabled": True},
            {"key": Key.ORDER_CANCEL_APPROVED_TECHNICIAN, "title": "تأیید لغو - تکنسین", "payer": Payer.COMPANY, "default_company_sms_enabled": False},
            {"key": Key.ORDER_CANCEL_REJECTED_TECHNICIAN, "title": "رد لغو - تکنسین", "payer": Payer.COMPANY, "default_company_sms_enabled": False},
            {"key": Key.INVOICE_ISSUED_CUSTOMER, "title": "صدور فاکتور - مشتری", "payer": Payer.COMPANY, "default_company_sms_enabled": True},
            {"key": Key.PAYMENT_SUCCESS_CUSTOMER, "title": "پرداخت موفق - مشتری", "payer": Payer.COMPANY, "default_company_sms_enabled": True},
            {"key": Key.PAYMENT_FAILED_CUSTOMER, "title": "پرداخت ناموفق - مشتری", "payer": Payer.COMPANY, "default_company_sms_enabled": True},
            {"key": Key.SURVEY_REQUEST_CUSTOMER, "title": "نظرسنجی - مشتری", "payer": Payer.COMPANY, "default_company_sms_enabled": False},

            {"key": Key.SMS_CREDIT_LOW_ADMIN, "title": "کم بودن اعتبار پیامک - مدیر شرکت", "payer": Payer.PLATFORM, "default_company_sms_enabled": True},
            {"key": Key.SMS_CREDIT_EMPTY_ADMIN, "title": "اتمام اعتبار پیامک - مدیر شرکت", "payer": Payer.PLATFORM, "default_company_sms_enabled": True},
            {"key": Key.SUBSCRIPTION_EXPIRING_ADMIN, "title": "نزدیک شدن پایان اشتراک - مدیر شرکت", "payer": Payer.PLATFORM, "default_company_sms_enabled": True},
            {"key": Key.SUBSCRIPTION_EXPIRED_ADMIN, "title": "پایان اشتراک - مدیر شرکت", "payer": Payer.PLATFORM, "default_company_sms_enabled": True},
            {"key": Key.PLATFORM_PAYMENT_SUCCESS_ADMIN, "title": "پرداخت موفق پلتفرمی - مدیر شرکت", "payer": Payer.PLATFORM, "default_company_sms_enabled": True},
            {"key": Key.PASSWORD_RESET, "title": "بازیابی رمز عبور", "payer": Payer.PLATFORM, "default_company_sms_enabled": True},
        ]

    @staticmethod
    def ensure_defaults() -> list[PlatformSMSMessageTypeSetting]:
        rows = []
        for item in PlatformSMSMessageTypeService.default_rows():
            row, _created = PlatformSMSMessageTypeSetting.objects.get_or_create(
                key=str(item["key"]),
                defaults={
                    "title": item["title"],
                    "payer": item["payer"],
                    "is_active": True,
                    "default_company_sms_enabled": item["default_company_sms_enabled"],
                },
            )
            if not row.title:
                row.title = item["title"]
                row.save(update_fields=["title", "updated_at"])
            rows.append(row)
        return rows

    @staticmethod
    def get_setting(*, template_key: str = "") -> Optional[PlatformSMSMessageTypeSetting]:
        if not template_key:
            return None
        PlatformSMSMessageTypeService.ensure_defaults()
        return PlatformSMSMessageTypeSetting.objects.filter(key=str(template_key)).first()

    @staticmethod
    def is_globally_enabled(*, template_key: str = "") -> bool:
        setting = PlatformSMSMessageTypeService.get_setting(template_key=template_key)
        return True if setting is None else bool(setting.is_active)

    @staticmethod
    def has_custom_window(*, template_key: str = "") -> bool:
        setting = PlatformSMSMessageTypeService.get_setting(template_key=template_key)
        return bool(setting and (setting.send_start_time or setting.send_end_time))

    @staticmethod
    def calculate_send_at(*, template_key: str = ""):
        setting = PlatformSMSMessageTypeService.get_setting(template_key=template_key)
        if setting is None or not setting.send_start_time or not setting.send_end_time:
            return None
        now = timezone.localtime()
        start = setting.send_start_time
        end = setting.send_end_time
        if start <= now.time() <= end:
            return None
        if now.time() < start:
            return now.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
        from datetime import timedelta
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)

    @staticmethod
    def apply_company_sms_defaults() -> int:
        from apps.notifications.models import NotificationSetting
        from apps.notifications.services import NotificationSettingService
        from apps.tenants.models import Company
        defaults = {
            str(item["key"]): bool(item["default_company_sms_enabled"])
            for item in PlatformSMSMessageTypeService.default_rows()
            if str(item["payer"]) == PlatformSMSMessageTypeSetting.Payer.COMPANY
        }
        changed = 0
        for company in Company.objects.all():
            NotificationSettingService.ensure_defaults(company=company)
            for key, enabled in defaults.items():
                changed += NotificationSetting.objects.filter(company=company, event_key=key).update(sms_enabled=enabled)
        return changed


class PlatformSMSProviderService:
    @staticmethod
    def get_active_provider() -> Optional[PlatformSMSProviderSetting]:
        return PlatformSMSProviderSetting.objects.filter(is_active=True).order_by("id").first()

    @staticmethod
    def get_or_create_singleton() -> PlatformSMSProviderSetting:
        provider = PlatformSMSProviderSetting.objects.order_by("id").first()
        if provider is None:
            provider = PlatformSMSProviderSetting.objects.create(
                name="Platform Fake SMS Provider",
                provider_type=PlatformSMSProviderSetting.ProviderType.FAKE,
                api_key="test",
                sender_number="1000",
                is_active=False,
            )
        return provider


class PlatformSMSQueueService:
    @staticmethod
    def queue(*, recipient_company=None, phone_number: str, message: str, template_key: str) -> Optional[PlatformSMSOutbox]:
        setting = PlatformSMSMessageTypeService.get_setting(template_key=template_key)
        if setting is not None and not setting.is_active:
            return None
        if setting is not None and setting.payer != PlatformSMSMessageTypeSetting.Payer.PLATFORM:
            raise ValueError("PlatformSMSQueueService can only queue platform-paid events.")

        normalized = normalize_platform_sms_phone(phone_number)
        if normalized is None:
            return PlatformSMSOutbox.objects.create(
                recipient_company=recipient_company,
                template_key=template_key,
                phone_number=(phone_number or "")[:15],
                message=message or "",
                status=PlatformSMSOutbox.Status.FAILED,
                error_message="شماره تلفن گیرنده معتبر نیست.",
                failed_at=timezone.now(),
            )

        return PlatformSMSOutbox.objects.create(
            recipient_company=recipient_company,
            template_key=template_key,
            phone_number=normalized,
            message=message or "",
            status=PlatformSMSOutbox.Status.QUEUED,
            send_at=PlatformSMSMessageTypeService.calculate_send_at(template_key=template_key),
        )


class PlatformSMSSendService:
    @staticmethod
    def _mark_failed(*, sms: PlatformSMSOutbox, error_message: str) -> PlatformSMSOutbox:
        now = timezone.now()
        sms.status = PlatformSMSOutbox.Status.FAILED
        sms.error_message = error_message
        sms.failed_at = now
        sms.last_attempt_at = now
        sms.save(update_fields=["status", "error_message", "failed_at", "last_attempt_at", "updated_at"])
        return sms

    @staticmethod
    def send(*, sms: PlatformSMSOutbox) -> PlatformSMSOutbox:
        if sms.status in (PlatformSMSOutbox.Status.SENT, PlatformSMSOutbox.Status.DELIVERED, PlatformSMSOutbox.Status.CANCELLED):
            return sms
        if sms.status not in (PlatformSMSOutbox.Status.QUEUED, PlatformSMSOutbox.Status.FAILED):
            return sms

        with transaction.atomic():
            locked = PlatformSMSOutbox.objects.select_for_update().get(pk=sms.pk)
            if locked.status in (PlatformSMSOutbox.Status.SENT, PlatformSMSOutbox.Status.DELIVERED, PlatformSMSOutbox.Status.CANCELLED):
                return locked
            now = timezone.now()
            locked.status = PlatformSMSOutbox.Status.SENDING
            locked.sending_at = now
            locked.last_attempt_at = now
            locked.attempt_count = (locked.attempt_count or 0) + 1
            locked.error_message = ""
            locked.save(update_fields=["status", "sending_at", "last_attempt_at", "attempt_count", "error_message", "updated_at"])

        sms = PlatformSMSOutbox.objects.get(pk=sms.pk)
        provider = PlatformSMSProviderService.get_active_provider()
        if provider is None:
            return PlatformSMSSendService._mark_failed(sms=sms, error_message="ارائه‌دهنده پیامک مالک پلتفرم فعال نیست.")

        provider_impl = get_sms_provider(provider)
        if provider_impl is None:
            return PlatformSMSSendService._mark_failed(sms=sms, error_message=f"پیاده‌سازی ارائه‌دهنده پیامک یافت نشد: {provider.provider_type}")

        sms.provider = provider
        sms.save(update_fields=["provider", "updated_at"])

        try:
            response = provider_impl.send(SMSSendRequest(phone_number=sms.phone_number, message=sms.message))
        except Exception as exc:
            return PlatformSMSSendService._mark_failed(sms=sms, error_message=str(exc))

        if response.success:
            sms.status = PlatformSMSOutbox.Status.SENT
            sms.provider_message_id = response.message_id or ""
            sms.sent_at = timezone.now()
            sms.error_message = ""
            sms.save(update_fields=["status", "provider_message_id", "sent_at", "error_message", "updated_at"])
        else:
            PlatformSMSSendService._mark_failed(sms=sms, error_message=response.error_message or "ارسال پیامک پلتفرمی ناموفق بود.")
        return sms


class PlatformSMSOutboxProcessorService:
    @staticmethod
    def process(*, limit: int = 100, dry_run: bool = False) -> dict:
        now = timezone.now()
        qs = PlatformSMSOutbox.objects.filter(status=PlatformSMSOutbox.Status.QUEUED).filter(
            Q(send_at__isnull=True) | Q(send_at__lte=now)
        ).order_by("created_at")
        ids = list(qs.values_list("id", flat=True)[:limit])
        results = {"scanned": 0, "sent": 0, "failed": 0, "skipped": 0, "dry_run": dry_run}
        for sms_id in ids:
            sms = PlatformSMSOutbox.objects.filter(id=sms_id).first()
            if sms is None:
                continue
            results["scanned"] += 1
            if dry_run:
                results["skipped"] += 1
                continue
            result = PlatformSMSSendService.send(sms=sms)
            if result.status in (PlatformSMSOutbox.Status.SENT, PlatformSMSOutbox.Status.DELIVERED):
                results["sent"] += 1
            elif result.status == PlatformSMSOutbox.Status.FAILED:
                results["failed"] += 1
            else:
                results["skipped"] += 1
        return results
