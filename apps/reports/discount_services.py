from __future__ import annotations

import hashlib
import hmac
import secrets
from decimal import Decimal
from typing import Iterable

from django.conf import settings
from django.db import transaction
from django.template import Context, Template
from django.utils import timezone

from apps.sms.services import SMSQueueService, normalize_sms_phone_number

from .models import DiscountCampaign, DiscountCampaignAllowedPhone, DiscountCampaignRecipient, DiscountCode

def _discount_campaign_format_rial(value):
    try:
        value = str(value).replace(",", "").replace("٬", "").strip()
        return f"{int(value):,}"
    except Exception:
        return str(value)


DISCOUNT_SMS_TEMPLATE_KEY = "discount_code_customer"
DISCOUNT_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789"
DEFAULT_DISCOUNT_MESSAGE_TEMPLATE = """{{ company_name }}
کد تخفیف شما: {{ discount_code }}
تخفیف {{ percent }}٪ تا سقف {{ max_discount_rial }} ریال
اعتبار تا {{ expires_at }}
"""


def normalize_discount_code(value: str) -> str:
    return (value or "").strip().replace(" ", "")


def normalize_campaign_code(value: str) -> str:
    """Normalize a custom campaign code: uppercase English, strip spaces, keep alphanumeric only."""
    v = (value or "").strip().upper().replace(" ", "").replace("\t", "")
    return "".join(ch for ch in v if ch.isalnum())


def generate_discount_code(length: int = 8) -> str:
    length = min(max(int(length or 8), 4), 8)
    return "".join(secrets.choice(DISCOUNT_CODE_ALPHABET) for _ in range(length))


def hash_discount_code(*, company_id: int, code: str) -> str:
    raw = f"{company_id}:{normalize_discount_code(code)}".encode("utf-8")
    secret = str(getattr(settings, "SECRET_KEY", "rasticlean")).encode("utf-8")
    return hmac.new(secret, raw, hashlib.sha256).hexdigest()


def mask_discount_code(code: str) -> str:
    code = normalize_discount_code(code)
    if not code:
        return "********"
    if len(code) <= 4:
        return "*" * len(code)
    return ("*" * (len(code) - 4)) + code[-4:]


def mask_discount_sms_text(message: str) -> str:
    text = message or ""
    # Handles the default template and keeps the rest of the SMS readable.
    import re
    text = re.sub(r"(کد\s*تخفیف\s*شما\s*[:：]\s*)([A-Za-z0-9]{4,12})", r"\1********", text)
    text = re.sub(r"(کد\s*[:：]\s*)([A-Za-z0-9]{4,12})", r"\1********", text)
    return text


def format_discount_expiry(value) -> str:
    if not value:
        return "-"
    try:
        from apps.common.jalali import format_jalali_date
        return format_jalali_date(timezone.localdate(value))
    except Exception:
        try:
            return timezone.localtime(value).strftime("%Y/%m/%d")
        except Exception:
            return str(value)


def _render_message(*, campaign: DiscountCampaign, code: str, customer_name: str, phone_number: str) -> str:
    template_text = campaign.message_template or DEFAULT_DISCOUNT_MESSAGE_TEMPLATE
    ctx = {
        "company_name": campaign.company.name,
        "company_code": campaign.company.code,
        "customer_name": customer_name,
        "customer_phone": phone_number,
        "discount_code": code,
        "percent": campaign.percent,
        "max_discount_rial": campaign.max_discount_rial,
        "expires_at": format_discount_expiry(campaign.expires_at),
    }
    return Template(template_text).render(Context(ctx)).strip()


class DiscountCampaignService:
    @staticmethod
    def create_campaign(
        *,
        company,
        title: str,
        source: str,
        percent,
        max_discount_rial,
        expires_at,
        recipients: list[dict],
        selected_customer_ids: set[int] | None,
        created_by=None,
        filter_snapshot: dict | None = None,
        message_template: str = "",
        custom_code: str = "",
    ) -> DiscountCampaign:
        selected_customer_ids = selected_customer_ids or set()
        username = getattr(created_by, "username", "") or ""
        user_id = getattr(created_by, "id", None)

        normalized_custom_code = normalize_campaign_code(custom_code)
        if not normalized_custom_code:
            raise ValueError("کد تخفیف الزامی است و نمی‌تواند خالی باشد.")

        with transaction.atomic():
            campaign = DiscountCampaign.objects.create(
                company=company,
                title=title or "کمپین تخفیف",
                source=source,
                status=DiscountCampaign.Status.DRAFT,
                percent=percent,
                max_discount_rial=int(max_discount_rial or 0),
                expires_at=expires_at,
                message_template=message_template or DEFAULT_DISCOUNT_MESSAGE_TEMPLATE,
                filter_snapshot=filter_snapshot or {},
                created_by_id=user_id,
                created_by_username=username,
                recipient_total=len(recipients),
                custom_code=normalized_custom_code,
            )

            excluded_total = 0
            code_total = 0
            sms_total = 0

            for item in recipients:
                customer_id = int(item.get("customer_id") or 0)
                included = (not selected_customer_ids) or (customer_id in selected_customer_ids)
                recipient = DiscountCampaignRecipient.objects.create(
                    company=company,
                    campaign=campaign,
                    customer_id=customer_id or None,
                    customer_name_snapshot=item.get("name", "") or "",
                    phone_number=item.get("phone", "") or "",
                    email_snapshot=item.get("email", "") or "",
                    last_address_snapshot=item.get("last_address", "") or "",
                    status=DiscountCampaignRecipient.Status.SELECTED if included else DiscountCampaignRecipient.Status.EXCLUDED,
                    excluded_by_id=None if included else user_id,
                    excluded_by_username="" if included else username,
                    excluded_at=None if included else timezone.now(),
                    exclusion_reason="" if included else "حذف دستی قبل از ارسال",
                )

                if not included:
                    excluded_total += 1
                    continue

                phone_number = recipient.phone_number
                normalized_phone = normalize_sms_phone_number(phone_number) or phone_number

                DiscountCampaignAllowedPhone.objects.get_or_create(
                    campaign=campaign,
                    normalized_phone=normalized_phone,
                    defaults={
                        "company": company,
                        "phone": phone_number,
                        "customer_id": customer_id or None,
                    },
                )
                recipient.status = DiscountCampaignRecipient.Status.CODE_CREATED
                recipient.save(update_fields=["status", "updated_at"])
                code_total += 1

                sms = DiscountCodeService.queue_sms_direct(
                    campaign=campaign,
                    phone_number=normalized_phone,
                    code=normalized_custom_code,
                    customer_name=recipient.customer_name_snapshot,
                )
                if sms is not None:
                    recipient.sms_outbox_id = sms.id
                    recipient.status = DiscountCampaignRecipient.Status.SMS_QUEUED
                    recipient.save(update_fields=["sms_outbox_id", "status", "updated_at"])
                    sms_total += 1

            campaign.excluded_total = excluded_total
            campaign.code_total = code_total
            campaign.sms_queued_total = sms_total
            campaign.status = DiscountCampaign.Status.QUEUED if sms_total else DiscountCampaign.Status.PARTIAL
            campaign.sent_at = timezone.now()
            campaign.save(update_fields=[
                "excluded_total", "code_total", "sms_queued_total", "status", "sent_at", "updated_at",
            ])
            return campaign


class DiscountCodeService:
    @staticmethod
    def create_code(*, company, campaign, customer_id, customer_name: str, phone_number: str, percent, max_discount_rial, expires_at) -> dict:
        for _ in range(20):
            raw_code = generate_discount_code(8)
            code_hash = hash_discount_code(company_id=company.id, code=raw_code)
            if not DiscountCode.objects.filter(company=company, code_hash=code_hash).exists():
                normalized_phone = normalize_sms_phone_number(phone_number) or (phone_number or "")
                discount_code = DiscountCode.objects.create(
                    company=company,
                    campaign=campaign,
                    customer_id=customer_id,
                    customer_name_snapshot=customer_name or "",
                    phone_number=normalized_phone,
                    code_hash=code_hash,
                    code_masked=mask_discount_code(raw_code),
                    percent=percent,
                    max_discount_rial=int(max_discount_rial or 0),
                    expires_at=expires_at,
                    status=DiscountCode.Status.CREATED,
                )
                return {"discount_code": discount_code, "raw_code": raw_code}

        raise ValueError("ساخت کد تخفیف یکتا ناموفق بود.")

    @staticmethod
    def queue_sms_direct(*, campaign: DiscountCampaign, phone_number: str, code: str, customer_name: str = ""):
        """Queue SMS for a custom campaign code (no DiscountCode record required)."""
        message = _render_message(
            campaign=campaign,
            code=code,
            customer_name=customer_name,
            phone_number=phone_number,
        )
        return SMSQueueService.queue(
            company=campaign.company,
            phone_number=phone_number,
            message=message,
            template_key=DISCOUNT_SMS_TEMPLATE_KEY,
        )

    @staticmethod
    def queue_sms_for_code(*, campaign: DiscountCampaign, discount_code: DiscountCode, raw_code: str, customer_name: str = ""):
        message = _render_message(
            campaign=campaign,
            code=raw_code,
            customer_name=customer_name or discount_code.customer_name_snapshot,
            phone_number=discount_code.phone_number,
        )
        sms = SMSQueueService.queue(
            company=campaign.company,
            phone_number=discount_code.phone_number,
            message=message,
            template_key=DISCOUNT_SMS_TEMPLATE_KEY,
        )
        if sms is not None:
            discount_code.sms_outbox_id = sms.id
            discount_code.status = DiscountCode.Status.SMS_QUEUED
            discount_code.save(update_fields=["sms_outbox_id", "status", "updated_at"])
        return sms

    @staticmethod
    @transaction.atomic
    def _apply_campaign_code(*, company, invoice, campaign: DiscountCampaign) -> tuple[bool, str, int]:
        """Apply a campaign-level custom code to an invoice, checking the phone whitelist."""
        if campaign.expires_at and campaign.expires_at < timezone.now():
            return False, "مهلت استفاده از این کد تخفیف تمام شده است.", 0

        invoice_phone = normalize_sms_phone_number(getattr(invoice, "display_customer_phone", "") or "") or ""

        has_whitelist = campaign.allowed_phones.exists()
        if has_whitelist:
            if not invoice_phone:
                return False, "این کد تخفیف برای شماره موبایل شما فعال نیست.", 0

            allowed = (
                DiscountCampaignAllowedPhone.objects
                .select_for_update()
                .filter(campaign=campaign, normalized_phone=invoice_phone)
                .first()
            )
            if allowed is None:
                return False, "این کد تخفیف برای شماره موبایل شما فعال نیست.", 0

            if allowed.used_at is not None:
                if allowed.used_invoice_id == invoice.id:
                    return True, "کد تخفیف قبلاً برای این فاکتور اعمال شده است.", int(allowed.used_discount_amount_rial or 0)
                return False, "این کد تخفیف قبلاً توسط شما استفاده شده است.", 0

        base_amount = int(getattr(invoice, "total_amount", 0) or 0)
        if base_amount <= 0:
            return False, "مبلغ فاکتور برای اعمال تخفیف معتبر نیست.", 0

        percent_amount = int((Decimal(base_amount) * Decimal(campaign.percent)) / Decimal("100"))
        discount_amount = min(percent_amount, int(campaign.max_discount_rial or 0))
        if discount_amount <= 0:
            return False, "مبلغ تخفیف برای این فاکتور صفر است.", 0

        invoice.campaign_discount_amount = int(getattr(invoice, "campaign_discount_amount", 0) or 0) + discount_amount
        invoice.recalculate_totals(save=True)

        if has_whitelist and allowed:
            allowed.used_at = timezone.now()
            allowed.used_invoice_id = invoice.id
            allowed.used_discount_amount_rial = discount_amount
            allowed.save(update_fields=["used_at", "used_invoice_id", "used_discount_amount_rial"])

        return True, f"کد تخفیف اعمال شد. مبلغ تخفیف: {discount_amount:,} ریال", discount_amount

    @staticmethod
    @transaction.atomic
    def apply_to_invoice(*, company, invoice, raw_code: str) -> tuple[bool, str, int]:
        code_value = normalize_discount_code(raw_code)
        if not code_value:
            return False, "کد تخفیف را وارد کنید.", 0

        if getattr(invoice, "company_id", None) != company.id:
            return False, "فاکتور متعلق به این شرکت نیست.", 0

        if getattr(invoice, "status", "") != "issued":
            return False, "کد تخفیف فقط برای فاکتور صادرشده و پرداخت‌نشده قابل استفاده است.", 0

        code_hash = hash_discount_code(company_id=company.id, code=code_value)
        discount_code = (
            DiscountCode.objects
            .select_for_update()
            .filter(company=company, code_hash=code_hash)
            .first()
        )
        if discount_code is None:
            # Try custom campaign code path — multiple campaigns may share the same code.
            # Find non-expired campaigns with this code for this company, then pick the one
            # whose whitelist includes the invoice phone. If multiple qualify, use the newest.
            normalized_custom = normalize_campaign_code(code_value)
            if not normalized_custom:
                return False, "کد تخفیف معتبر نیست.", 0
            now = timezone.now()
            matching_campaigns = list(
                DiscountCampaign.objects.filter(
                    company=company,
                    custom_code=normalized_custom,
                    expires_at__gt=now,
                ).exclude(status=DiscountCampaign.Status.CANCELLED)
                .order_by("-id")
            )
            if not matching_campaigns:
                return False, "کد تخفیف معتبر نیست.", 0

            invoice_phone = normalize_sms_phone_number(
                getattr(invoice, "display_customer_phone", "") or ""
            ) or ""

            # Find first campaign (newest first) where this phone is whitelisted
            target_campaign = None
            for c in matching_campaigns:
                if c.allowed_phones.filter(normalized_phone=invoice_phone).exists():
                    target_campaign = c
                    break

            if target_campaign is None:
                return False, "این کد تخفیف برای شماره موبایل شما فعال نیست.", 0

            return DiscountCodeService._apply_campaign_code(
                company=company, invoice=invoice, campaign=target_campaign
            )

        if discount_code.status == DiscountCode.Status.USED:
            # TODO (minimal idempotency fix): if the code was already applied to THIS
            # invoice, return success instead of an error so that page reloads and
            # retries don't confuse the user.
            #
            # NOTE: This is a temporary minimal fix. The robust design should introduce
            # a PENDING/RESERVED state so the code is not fully burned until the payment
            # is confirmed by the gateway. In this phase (no real gateway) the current
            # behaviour is acceptable: discount is applied to the invoice and stays even
            # if the customer doesn't pay immediately.
            if discount_code.used_invoice_id == invoice.id:
                return True, "کد تخفیف قبلاً برای این فاکتور اعمال شده است.", int(discount_code.used_discount_amount_rial or 0)
            return False, "این کد تخفیف قبلاً استفاده شده است.", 0
        if discount_code.status == DiscountCode.Status.CANCELLED:
            return False, "این کد تخفیف لغو شده است.", 0
        if discount_code.expires_at and discount_code.expires_at < timezone.now():
            discount_code.status = DiscountCode.Status.EXPIRED
            discount_code.save(update_fields=["status", "updated_at"])
            return False, "مهلت استفاده از این کد تخفیف تمام شده است.", 0

        invoice_phone = normalize_sms_phone_number(getattr(invoice, "display_customer_phone", "") or "") or (getattr(invoice, "display_customer_phone", "") or "")
        code_phone = normalize_sms_phone_number(discount_code.phone_number) or discount_code.phone_number
        if invoice_phone and code_phone and invoice_phone != code_phone:
            return False, "این کد تخفیف برای شماره موبایل این فاکتور نیست.", 0

        base_amount = int(getattr(invoice, "total_amount", 0) or 0)
        if base_amount <= 0:
            return False, "مبلغ فاکتور برای اعمال تخفیف معتبر نیست.", 0

        percent_amount = int((Decimal(base_amount) * Decimal(discount_code.percent)) / Decimal("100"))
        discount_amount = min(percent_amount, int(discount_code.max_discount_rial or 0))
        if discount_amount <= 0:
            return False, "مبلغ تخفیف برای این فاکتور صفر است.", 0

        # Important business rule:
        # This is an invoice-level discount. It does NOT modify invoice items,
        # so technician wage calculations based on service/goods/travel rows remain unchanged.
        invoice.campaign_discount_amount = int(getattr(invoice, "campaign_discount_amount", 0) or 0) + discount_amount
        invoice.recalculate_totals(save=True)

        discount_code.status = DiscountCode.Status.USED
        discount_code.used_invoice_id = invoice.id
        discount_code.used_discount_amount_rial = discount_amount
        discount_code.used_at = timezone.now()
        discount_code.save(update_fields=[
            "status", "used_invoice_id", "used_discount_amount_rial", "used_at", "updated_at",
        ])

        return True, f"کد تخفیف اعمال شد. مبلغ تخفیف: {discount_amount:,} ریال", discount_amount
