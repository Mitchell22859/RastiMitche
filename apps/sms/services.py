"""
SMS service layer.

Clean outbox architecture:
- Event code only queues SMSOutbox rows.
- The worker/command processes queued rows.
- Company SMS wallet is checked immediately before sending.
- Provider is always selected from sms.company, never from another company.
"""
import math
import re
from typing import Optional, Tuple

from django.db import transaction
from django.db.models import Q
from django.template import Context, Template
from django.utils import timezone

from .models import SMSOutbox, SMSProvider, SMSTemplate
from .providers import get_sms_provider
from .providers.base import SMSSendRequest
from .selectors import SMSProviderSelector


_IRAN_MOBILE_REGEX = re.compile(r"^09[0-9]{9}$")


def normalize_sms_phone_number(raw: str) -> Optional[str]:
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


def validate_sms_phone_number(raw: str) -> Tuple[bool, str, str]:
    if not raw or not raw.strip():
        return False, "", "شماره گیرنده الزامی است."

    normalized = normalize_sms_phone_number(raw)
    if normalized is None:
        return False, "", "شماره تلفن وارد شده معتبر نیست. فرمت صحیح: 09xxxxxxxxx"

    return True, normalized, ""



SMS_PRICING_SNAPSHOT_FIELDS = [
    "message_length_snapshot",
    "sms_parts_snapshot",
    "sms_cost_rial_snapshot",
    "pricing_characters_per_sms_snapshot",
    "pricing_price_per_sms_rial_snapshot",
    "pricing_snapshot_at",
]


def build_sms_pricing_snapshot(message_text: str) -> dict:
    """Capture current SMS pricing for a real send attempt.

    Important business rule:
    queued SMS rows do NOT have a final price. Their UI cost is only an
    estimate based on the current platform pricing. The final pricing snapshot
    must be written only when the worker actually tries to send the SMS.

    Therefore, if a message was queued days ago but is sent today, today's
    owner-defined characters_per_sms and price_per_sms_rial are used. Once the
    SMS becomes sent/failed for that attempt, the snapshot remains fixed.
    """
    try:
        from apps.platform_core.services_sms_credit import SMSCreditService
        pricing = SMSCreditService.get_pricing()
        chars_per_sms = int(getattr(pricing, "characters_per_sms", 0) or 0)
        price_per_sms = int(getattr(pricing, "price_per_sms_rial", 0) or 0)
    except Exception:
        chars_per_sms = 0
        price_per_sms = 0

    text = message_text or ""
    length = len(text)
    parts = int(math.ceil(length / chars_per_sms)) if length > 0 and chars_per_sms > 0 else 0
    cost = int(parts * price_per_sms)
    return {
        "message_length_snapshot": length,
        "sms_parts_snapshot": parts,
        "sms_cost_rial_snapshot": cost,
        "pricing_characters_per_sms_snapshot": chars_per_sms,
        "pricing_price_per_sms_rial_snapshot": price_per_sms,
        "pricing_snapshot_at": timezone.now(),
    }


class SMSEventSwitchService:
    # Company-level switch for each SMS event.
    # If a company disables an SMS event, no SMSOutbox row is created.

    @staticmethod
    def _controlled_keys() -> set[str]:
        return {str(value) for value, _label in SMSTemplate.TemplateKey.choices}

    @staticmethod
    def is_enabled(*, company, template_key: str = "") -> bool:
        if company is None:
            return False

        key = str(template_key or "").strip()
        if not key:
            return True

        try:
            from apps.platform_core.services_platform_sms import PlatformSMSMessageTypeService
            if not PlatformSMSMessageTypeService.is_globally_enabled(template_key=key):
                return False
        except Exception:
            pass

        # Diagnostic/manual internal keys are not company event types.
        if key not in SMSEventSwitchService._controlled_keys():
            return True

        try:
            from apps.notifications.models import NotificationSetting
            from apps.notifications.services import NotificationSettingService
        except Exception:
            # Safe default for app-loading edge cases. Runtime uses the normal path.
            return True

        NotificationSettingService.ensure_defaults(company=company)
        setting = NotificationSetting.objects.filter(company=company, event_key=key).first()
        if setting is None:
            return True

        return bool(setting.sms_enabled)


class SMSQueueService:
    """
    Queue an SMS. This does not check or debit SMS wallet.
    Wallet is checked by SMSSendService immediately before sending.
    """

    @staticmethod
    def queue(
        *,
        company,
        phone_number: str,
        message: str,
        template: Optional[SMSTemplate] = None,
        template_key: str = "",
        send_at=None,
        order_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
    ) -> Optional[SMSOutbox]:
        if company is None:
            raise ValueError("SMSQueueService.queue requires company.")

        # Important: if this is a controlled event and the company has disabled
        # SMS for it, do not create any SMSOutbox row.
        if not SMSEventSwitchService.is_enabled(company=company, template_key=template_key):
            return None

        # If caller passed an inactive template directly, do not queue it.
        if template is not None and not template.is_active:
            return None

        message_text = message or ""

        normalized = normalize_sms_phone_number(phone_number)
        if normalized is None:
            return SMSOutbox.objects.create(
                company=company,
                template=template,
                template_key=template_key or "",
                phone_number=(phone_number or "")[:15],
                message=message_text,
                status=SMSOutbox.Status.FAILED,
                error_message="شماره تلفن گیرنده معتبر نیست.",
                failed_at=timezone.now(),
                send_at=send_at,
                order_id=order_id,
                invoice_id=invoice_id,
            )

        # Do not snapshot price at queue time.
        # A queued SMS may be sent later and must use the pricing active at
        # the actual send attempt. UI may show an estimate while queued.
        return SMSOutbox.objects.create(
            company=company,
            template=template,
            template_key=template_key or "",
            phone_number=normalized,
            message=message_text,
            status=SMSOutbox.Status.QUEUED,
            queued_at=timezone.now(),
            send_at=send_at,
            order_id=order_id,
            invoice_id=invoice_id,
        )


class SMSSendingSafetyService:
    DISABLED_ERROR = "ارسال پیامک برای این شرکت غیرفعال است؛ ارائه‌دهنده فعال یافت نشد."

    @staticmethod
    def get_active_provider(*, company) -> Optional[SMSProvider]:
        return SMSProviderSelector.get_active_for_company(company=company)

    @staticmethod
    def is_sending_enabled(*, company) -> bool:
        return SMSSendingSafetyService.get_active_provider(company=company) is not None

    @staticmethod
    def get_status(*, company) -> dict:
        provider = SMSSendingSafetyService.get_active_provider(company=company)
        if provider is None:
            return {"enabled": False, "reason": SMSSendingSafetyService.DISABLED_ERROR, "provider": None}
        return {"enabled": True, "reason": "", "provider": provider}


class SMSSendService:
    """
    Send one queued SMS.

    Important isolation rules:
    - Provider is selected from sms.company at send time.
    - sms.provider from old/stale data is not trusted.
    - Wallet debit uses sms.company only.
    """

    @staticmethod
    def _mark_failed(*, sms: SMSOutbox, error_message: str) -> SMSOutbox:
        now = timezone.now()
        sms.status = SMSOutbox.Status.FAILED
        sms.error_message = error_message
        sms.failed_at = now
        sms.last_attempt_at = now
        sms.save(update_fields=["status", "error_message", "failed_at", "last_attempt_at", "updated_at"])
        return sms

    @staticmethod
    def send(*, sms: SMSOutbox) -> SMSOutbox:
        if sms.status in (SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED, SMSOutbox.Status.CANCELLED):
            return sms

        if sms.status not in (SMSOutbox.Status.QUEUED, SMSOutbox.Status.FAILED):
            return sms

        now = timezone.now()
        with transaction.atomic():
            locked = SMSOutbox.objects.select_for_update().select_related("company").get(pk=sms.pk)

            if locked.status in (SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED, SMSOutbox.Status.CANCELLED):
                return locked

            locked.status = SMSOutbox.Status.SENDING
            locked.sending_at = now
            locked.last_attempt_at = now
            locked.attempt_count = (locked.attempt_count or 0) + 1
            locked.error_message = ""
            locked.save(update_fields=[
                "status", "sending_at", "last_attempt_at", "attempt_count", "error_message", "updated_at",
            ])

        sms = SMSOutbox.objects.select_related("company").get(pk=sms.pk)
        provider = SMSSendingSafetyService.get_active_provider(company=sms.company)
        if provider is None:
            return SMSSendService._mark_failed(sms=sms, error_message=SMSSendingSafetyService.DISABLED_ERROR)

        send_pricing_snapshot = build_sms_pricing_snapshot(sms.message)

        sms.provider = provider
        for field_name, value in send_pricing_snapshot.items():
            setattr(sms, field_name, value)
        sms.save(update_fields=["provider", *SMS_PRICING_SNAPSHOT_FIELDS, "updated_at"])

        provider_impl = get_sms_provider(provider)
        if provider_impl is None:
            return SMSSendService._mark_failed(
                sms=sms,
                error_message=f"پیاده‌سازی ارائه‌دهنده پیامک یافت نشد: {provider.provider_type}",
            )

        from apps.platform_core.services_sms_credit import SMSCreditService

        debit_ok, debit_tx, debit_error = SMSCreditService.try_debit_for_sms(
            company=sms.company,
            message_text=sms.message,
            description=f"ارسال پیامک به {sms.phone_number}",
            fixed_cost_rial=send_pricing_snapshot.get("sms_cost_rial_snapshot"),
            fixed_sms_parts=send_pricing_snapshot.get("sms_parts_snapshot"),
            fixed_message_length=send_pricing_snapshot.get("message_length_snapshot"),
        )
        if not debit_ok:
            return SMSSendService._mark_failed(sms=sms, error_message=debit_error)

        try:
            response = provider_impl.send(SMSSendRequest(phone_number=sms.phone_number, message=sms.message))
        except Exception as exc:
            SMSCreditService.refund_sms_debit(transaction=debit_tx, description=f"برگشت اعتبار پیامک ناموفق برای {sms.phone_number}")
            return SMSSendService._mark_failed(sms=sms, error_message=str(exc))

        if response.success:
            sms.status = SMSOutbox.Status.SENT
            sms.provider_message_id = response.message_id or ""
            sms.sent_at = timezone.now()
            sms.error_message = ""
            sms.save(update_fields=["status", "provider_message_id", "sent_at", "error_message", "updated_at"])
        else:
            SMSCreditService.refund_sms_debit(transaction=debit_tx, description=f"برگشت اعتبار پیامک ناموفق برای {sms.phone_number}")
            SMSSendService._mark_failed(sms=sms, error_message=response.error_message or "ارسال پیامک ناموفق بود.")

        return sms


class SMSBulkSendService:
    @staticmethod
    def send_all_queued(*, company) -> list[SMSOutbox]:
        return [
            SMSSendService.send(sms=sms)
            for sms in SMSOutbox.objects.filter(company=company, status=SMSOutbox.Status.QUEUED).order_by("created_at")
        ]

    send_all_pending = send_all_queued


class SMSTemplateRenderService:
    @staticmethod
    def render(*, template_text: str, context: dict) -> str:
        return Template(template_text).render(Context(context or {}))

    @staticmethod
    def build_order_context(*, order) -> dict:
        customer_name = getattr(order, "customer_name", "") or getattr(order, "display_customer_name", "") or ""
        customer_phone = getattr(order, "customer_phone", "") or getattr(order, "display_customer_phone", "") or ""

        technician_name = ""
        technician_phone = ""
        technician = getattr(order, "technician", None)
        technician_user = getattr(technician, "user", None)
        if technician_user:
            get_full_name = getattr(technician_user, "get_full_name", None)
            technician_name = ((get_full_name() if callable(get_full_name) else "") or getattr(technician_user, "full_name", "") or getattr(technician_user, "username", "") or "")
            technician_phone = getattr(technician_user, "phone", "") or getattr(technician_user, "mobile", "") or ""

        category = getattr(order, "service_category", None)

        return {
            "order_id": order.id,
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "technician_name": technician_name,
            "technician_phone": technician_phone,
            "service_category": getattr(category, "title", "") if category else "",
            "company_name": getattr(order.company, "name", ""),
            "company_code": getattr(order.company, "code", ""),
        }

    @staticmethod
    def build_invoice_context(*, invoice) -> dict:
        order = getattr(invoice, "order", None)
        customer_name = getattr(invoice, "customer_name_snapshot", "") or getattr(order, "customer_name", "") or ""
        customer_phone = getattr(invoice, "customer_phone_snapshot", "") or getattr(order, "customer_phone", "") or ""
        return {
            "invoice_id": invoice.id,
            "invoice_number": getattr(invoice, "invoice_number", "") or invoice.id,
            "invoice_amount": getattr(invoice, "total_amount", 0),
            "customer_name": customer_name,
            "customer_phone": customer_phone,
            "company_name": getattr(invoice.company, "name", ""),
            "company_code": getattr(invoice.company, "code", ""),
        }


class SMSTimeWindowService:
    @staticmethod
    def calculate_send_at(*, template: Optional[SMSTemplate]):
        try:
            from apps.platform_core.services_platform_sms import PlatformSMSMessageTypeService
            key = str(getattr(template, "key", "") or "")
            if key and PlatformSMSMessageTypeService.has_custom_window(template_key=key):
                return PlatformSMSMessageTypeService.calculate_send_at(template_key=key)
        except Exception:
            pass

        if template is None or not template.send_start_time or not template.send_end_time:
            return None

        now = timezone.localtime()
        start = template.send_start_time
        end = template.send_end_time

        if start <= now.time() <= end:
            return None

        if now.time() < start:
            return now.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)

        from datetime import timedelta
        tomorrow = now + timedelta(days=1)
        return tomorrow.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)


class SMSQueueFromTemplateService:
    @staticmethod
    def queue_from_template(
        *,
        company,
        template_key: str,
        phone_number: str,
        context: dict,
        fallback_message: str = "",
        order_id: Optional[int] = None,
        invoice_id: Optional[int] = None,
    ) -> Optional[SMSOutbox]:
        if company is None:
            raise ValueError("queue_from_template requires company.")

        # Business-level company switch.
        # If disabled, the message must NOT enter SMSOutbox.
        if not SMSEventSwitchService.is_enabled(company=company, template_key=template_key):
            return None

        from .template_resolver import resolve_effective_sms_template

        resolved = resolve_effective_sms_template(company=company, event_key=template_key)

        if resolved is not None:
            # Template-level switch: if resolved template is inactive, do not send
            if not resolved.get("is_active", True):
                return None

            message = SMSTemplateRenderService.render(
                template_text=resolved["text"],
                context=context or {},
            )
            # For send_at timing, use company template's time window if it's an approved override
            template_obj = resolved.get("template_obj")
            if resolved["source"] == "approved_override" and hasattr(template_obj, "send_start_time"):
                send_at = SMSTimeWindowService.calculate_send_at(template=template_obj)
            else:
                send_at = None
        else:
            message = fallback_message
            send_at = None

        if not message:
            return None

        normalized = normalize_sms_phone_number(phone_number) or phone_number

        # Only deduplicate waiting messages for the same company/event/object.
        duplicate = SMSOutbox.objects.filter(
            company=company,
            phone_number=normalized,
            template_key=template_key,
            order_id=order_id,
            invoice_id=invoice_id,
            status=SMSOutbox.Status.QUEUED,
        ).exists()
        if duplicate:
            return None

        return SMSQueueService.queue(
            company=company,
            phone_number=phone_number,
            message=message,
            template=resolved["template_obj"] if resolved and resolved["source"] == "approved_override" and isinstance(resolved["template_obj"], SMSTemplate) else None,
            template_key=template_key,
            send_at=send_at,
            order_id=order_id,
            invoice_id=invoice_id,
        )



class SMSEventHooks:
    @staticmethod
    def _first_admin_phone(company) -> str:
        from apps.accounts.models import CompanyUser, UserRole
        admin = CompanyUser.objects.filter(company=company, role=UserRole.COMPANY_ADMIN, is_active=True).order_by("id").first()
        return getattr(admin, "phone", "") if admin else ""

    @staticmethod
    def _technician_phone(order) -> str:
        user = getattr(getattr(order, "technician", None), "user", None)
        return getattr(user, "phone", "") or getattr(user, "mobile", "") or ""

    @staticmethod
    def _order_customer_phone(order) -> str:
        return getattr(order, "customer_phone", "") or getattr(order, "display_customer_phone", "") or ""

    @staticmethod
    def on_order_created(*, order) -> Optional[SMSOutbox]:
        phone = SMSEventHooks._first_admin_phone(order.company)
        if not phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_CREATED_ADMIN,
            phone_number=phone,
            context=context,
            fallback_message=f"سفارش جدید #{order.id} ثبت شد.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_assigned_technician(*, order) -> Optional[SMSOutbox]:
        phone = SMSEventHooks._technician_phone(order)
        if not phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_ASSIGNED_TECHNICIAN,
            phone_number=phone,
            context=context,
            fallback_message=f"سفارش #{order.id} به شما تخصیص داده شد.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_accepted(*, order) -> Optional[SMSOutbox]:
        phone = SMSEventHooks._order_customer_phone(order)
        if not phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_ACCEPTED_CUSTOMER,
            phone_number=phone,
            context=context,
            fallback_message=f"سفارش #{order.id} توسط نیروی خدماتی پذیرفته شد.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_completed(*, order) -> Optional[SMSOutbox]:
        phone = SMSEventHooks._order_customer_phone(order)
        if not phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_COMPLETED_CUSTOMER,
            phone_number=phone,
            context=context,
            fallback_message=f"سفارش #{order.id} تکمیل شد.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_cancel_requested_admin(*, order, reason: str = "") -> Optional[SMSOutbox]:
        phone = SMSEventHooks._first_admin_phone(order.company)
        if not phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        context["reason"] = reason or ""
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_CANCEL_REQUESTED_ADMIN,
            phone_number=phone,
            context=context,
            fallback_message=f"درخواست لغو سفارش #{order.id} ثبت شد.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_cancel_approved_technician(*, order) -> Optional[SMSOutbox]:
        phone = SMSEventHooks._technician_phone(order)
        if not phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_CANCEL_APPROVED_TECHNICIAN,
            phone_number=phone,
            context=context,
            fallback_message=f"درخواست لغو سفارش #{order.id} تأیید شد.",
            order_id=order.id,
        )

    @staticmethod
    def on_order_cancel_rejected_technician(*, order) -> Optional[SMSOutbox]:
        phone = SMSEventHooks._technician_phone(order)
        if not phone:
            return None
        context = SMSTemplateRenderService.build_order_context(order=order)
        return SMSQueueFromTemplateService.queue_from_template(
            company=order.company,
            template_key=SMSTemplate.TemplateKey.ORDER_CANCEL_REJECTED_TECHNICIAN,
            phone_number=phone,
            context=context,
            fallback_message=f"درخواست لغو سفارش #{order.id} رد شد.",
            order_id=order.id,
        )

    @staticmethod
    def on_invoice_issued(*, invoice) -> Optional[SMSOutbox]:
        context = SMSTemplateRenderService.build_invoice_context(invoice=invoice)
        phone = context.get("customer_phone") or ""
        if not phone:
            return None
        return SMSQueueFromTemplateService.queue_from_template(
            company=invoice.company,
            template_key=SMSTemplate.TemplateKey.INVOICE_ISSUED_CUSTOMER,
            phone_number=phone,
            context=context,
            fallback_message=f"فاکتور {context.get('invoice_number')} صادر شد. مبلغ: {context.get('invoice_amount')}",
            invoice_id=invoice.id,
        )

    @staticmethod
    def on_payment_success(*, invoice) -> Optional[SMSOutbox]:
        context = SMSTemplateRenderService.build_invoice_context(invoice=invoice)
        phone = context.get("customer_phone") or ""
        if not phone:
            return None
        return SMSQueueFromTemplateService.queue_from_template(
            company=invoice.company,
            template_key=SMSTemplate.TemplateKey.PAYMENT_SUCCESS_CUSTOMER,
            phone_number=phone,
            context=context,
            fallback_message=f"پرداخت فاکتور {context.get('invoice_number')} موفق بود.",
            invoice_id=invoice.id,
        )

    @staticmethod
    def on_payment_failed(*, invoice) -> Optional[SMSOutbox]:
        context = SMSTemplateRenderService.build_invoice_context(invoice=invoice)
        phone = context.get("customer_phone") or ""
        if not phone:
            return None
        return SMSQueueFromTemplateService.queue_from_template(
            company=invoice.company,
            template_key=SMSTemplate.TemplateKey.PAYMENT_FAILED_CUSTOMER,
            phone_number=phone,
            context=context,
            fallback_message=f"پرداخت فاکتور {context.get('invoice_number')} ناموفق بود.",
            invoice_id=invoice.id,
        )


class SMSOutboxProcessorService:
    @staticmethod
    def process(*, company=None, limit: int = 100, dry_run: bool = False) -> dict:
        now = timezone.now()
        qs = SMSOutbox.objects.filter(status=SMSOutbox.Status.QUEUED).filter(
            Q(send_at__isnull=True) | Q(send_at__lte=now)
        )

        if company is not None:
            qs = qs.filter(company=company)

        ids = list(qs.order_by("created_at").values_list("id", flat=True)[:limit])
        results = {"scanned": 0, "sent": 0, "failed": 0, "skipped": 0, "dry_run": dry_run}

        for sms_id in ids:
            sms = SMSOutbox.objects.filter(id=sms_id).select_related("company").first()
            if sms is None:
                continue

            results["scanned"] += 1
            if dry_run:
                results["skipped"] += 1
                continue

            result = SMSSendService.send(sms=sms)
            if result.status in (SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED):
                results["sent"] += 1
            elif result.status == SMSOutbox.Status.FAILED:
                results["failed"] += 1
            else:
                results["skipped"] += 1

        return results

    @staticmethod
    def send_single(*, sms: SMSOutbox) -> SMSOutbox:
        if sms.status in (SMSOutbox.Status.SENT, SMSOutbox.Status.DELIVERED):
            return sms

        if sms.status in (SMSOutbox.Status.FAILED, SMSOutbox.Status.CANCELLED):
            sms.status = SMSOutbox.Status.QUEUED
            sms.error_message = ""
            sms.failed_at = None
            sms.save(update_fields=["status", "error_message", "failed_at", "updated_at"])

        return SMSSendService.send(sms=sms)


class SMSDiagnosticsService:
    DIAGNOSTIC_TEMPLATE_KEY = "__diagnostic_test__"

    @staticmethod
    def get_provider_info(*, company) -> dict:
        provider = SMSProviderSelector.get_active_for_company(company=company)
        safety = SMSSendingSafetyService.get_status(company=company)
        if provider is None:
            return {"has_provider": False, "sending_enabled": False, "reason": safety["reason"]}
        return {
            "has_provider": True,
            "sending_enabled": safety["enabled"],
            "reason": safety["reason"],
            "provider_name": provider.name,
            "provider_type": provider.provider_type,
            "sender_number": provider.sender_number,
        }

    @staticmethod
    def send_test(*, company, phone_number: str, message: str, send_immediately: bool = False) -> dict:
        if not message:
            return {"success": False, "error": "متن پیام الزامی است.", "sms": None}

        sms = SMSQueueService.queue(
            company=company,
            phone_number=phone_number,
            message=message,
            template_key=SMSDiagnosticsService.DIAGNOSTIC_TEMPLATE_KEY,
        )
        if sms is None:
            return {"success": False, "error": "شماره موبایل معتبر نیست.", "sms": None}
        if sms.status == SMSOutbox.Status.FAILED:
            return {"success": False, "error": sms.error_message, "sms": sms}
        if send_immediately:
            sms = SMSOutboxProcessorService.send_single(sms=sms)
        return {"success": True, "error": "", "sms": sms}
