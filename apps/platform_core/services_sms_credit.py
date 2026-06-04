"""SMS Credit Wallet Service.

This service is company-scoped and used by the SMS outbox worker.
No SMS is debited when it is queued; debit happens immediately before provider send.
"""
import math
import uuid

from django.db import transaction
from django.utils import timezone

from .models import GlobalSMSPricingSetting, CompanySMSWallet, CompanySMSTransaction, PlatformBillingInvoice


class SMSCreditService:
    @staticmethod
    def get_pricing():
        pricing, _ = GlobalSMSPricingSetting.objects.get_or_create(pk=1)
        return pricing

    @staticmethod
    def get_or_create_wallet(company):
        wallet, _ = CompanySMSWallet.objects.get_or_create(company=company)
        return wallet

    @staticmethod
    def estimate_sms_parts(message_text: str) -> int:
        pricing = SMSCreditService.get_pricing()
        length = len(message_text or "")
        if length == 0:
            return 0
        return math.ceil(length / pricing.characters_per_sms)

    @staticmethod
    def estimate_message_cost(message_text: str) -> int:
        parts = SMSCreditService.estimate_sms_parts(message_text)
        pricing = SMSCreditService.get_pricing()
        return parts * pricing.price_per_sms_rial

    @staticmethod
    def get_remaining_sms_count(company) -> int:
        wallet = SMSCreditService.get_or_create_wallet(company)
        pricing = SMSCreditService.get_pricing()
        if pricing.price_per_sms_rial <= 0:
            return 0
        return wallet.balance_rial // pricing.price_per_sms_rial

    @staticmethod
    def has_sufficient_credit(company, message_text: str) -> bool:
        cost = SMSCreditService.estimate_message_cost(message_text)
        wallet = SMSCreditService.get_or_create_wallet(company)
        return wallet.balance_rial >= cost

    @staticmethod
    @transaction.atomic
    def try_debit_for_sms(
        company,
        message_text: str,
        description: str = "",
        *,
        fixed_cost_rial: int | None = None,
        fixed_sms_parts: int | None = None,
        fixed_message_length: int | None = None,
    ):
        """Debit SMS credit immediately before sending.

        The optional fixed_* values must represent the pricing snapshot captured
        for the current real send attempt. Queued SMS rows should not pass stale
        queue-time snapshots; they must be priced using the owner settings that
        are active at send time.
        """
        message_length = len(message_text or "") if fixed_message_length is None else int(fixed_message_length or 0)
        parts = SMSCreditService.estimate_sms_parts(message_text) if fixed_sms_parts is None else int(fixed_sms_parts or 0)
        cost = SMSCreditService.estimate_message_cost(message_text) if fixed_cost_rial is None else int(fixed_cost_rial or 0)

        wallet, _ = CompanySMSWallet.objects.select_for_update().get_or_create(company=company)

        if wallet.balance_rial < cost:
            tx = CompanySMSTransaction.objects.create(
                company=company,
                wallet=wallet,
                transaction_type=CompanySMSTransaction.TransactionType.BLOCKED,
                amount_rial=cost,
                sms_parts=parts,
                message_length=message_length,
                balance_after=wallet.balance_rial,
                description=description or "اعتبار پیامک ناکافی",
            )
            return False, tx, "اعتبار پیامک شرکت کافی نیست."

        wallet.balance_rial -= cost
        wallet.save(update_fields=["balance_rial", "updated_at"])

        tx = CompanySMSTransaction.objects.create(
            company=company,
            wallet=wallet,
            transaction_type=CompanySMSTransaction.TransactionType.DEBIT,
            amount_rial=cost,
            sms_parts=parts,
            message_length=message_length,
            balance_after=wallet.balance_rial,
            description=description or f"مصرف {parts} پیامک",
        )
        return True, tx, ""

    @staticmethod
    @transaction.atomic
    def refund_sms_debit(transaction: CompanySMSTransaction, description: str = ""):
        if transaction is None or transaction.transaction_type != CompanySMSTransaction.TransactionType.DEBIT or transaction.amount_rial <= 0:
            return None

        wallet = CompanySMSWallet.objects.select_for_update().get(pk=transaction.wallet_id)
        wallet.balance_rial += transaction.amount_rial
        wallet.save(update_fields=["balance_rial", "updated_at"])

        return CompanySMSTransaction.objects.create(
            company=transaction.company,
            wallet=wallet,
            transaction_type=CompanySMSTransaction.TransactionType.ADJUSTMENT,
            amount_rial=transaction.amount_rial,
            sms_parts=transaction.sms_parts,
            message_length=transaction.message_length,
            balance_after=wallet.balance_rial,
            description=description or "برگشت اعتبار پیامک ناموفق",
        )

    @staticmethod
    @transaction.atomic
    def debit_for_sms(company, message_text: str, description: str = "") -> CompanySMSTransaction:
        ok, tx, _ = SMSCreditService.try_debit_for_sms(
            company=company,
            message_text=message_text,
            description=description,
        )
        return tx

    @staticmethod
    @transaction.atomic
    def credit_wallet(company, amount_rial: int, invoice=None, created_by=None) -> CompanySMSTransaction:
        wallet = SMSCreditService.get_or_create_wallet(company)
        wallet.balance_rial += amount_rial
        wallet.save(update_fields=["balance_rial", "updated_at"])

        return CompanySMSTransaction.objects.create(
            company=company,
            wallet=wallet,
            transaction_type=CompanySMSTransaction.TransactionType.CREDIT,
            amount_rial=amount_rial,
            balance_after=wallet.balance_rial,
            description=f"شارژ {amount_rial:,} ریال",
            related_invoice=invoice,
            created_by=created_by,
        )

    @staticmethod
    def create_recharge_invoice(company, amount_rial: int, created_by=None) -> PlatformBillingInvoice:
        inv_number = f"SMS-{uuid.uuid4().hex[:8].upper()}"
        return PlatformBillingInvoice.objects.create(
            company=company,
            invoice_number=inv_number,
            invoice_type=PlatformBillingInvoice.InvoiceType.SMS_RECHARGE,
            amount_rial=amount_rial,
            status=PlatformBillingInvoice.Status.UNPAID,
            description=f"شارژ پیامک - {amount_rial:,} ریال",
            created_by=created_by,
        )

    @staticmethod
    @transaction.atomic
    def mark_invoice_paid(invoice: PlatformBillingInvoice, paid_by=None):
        if invoice.status == PlatformBillingInvoice.Status.PAID:
            return

        invoice.status = PlatformBillingInvoice.Status.PAID
        invoice.paid_by = paid_by
        invoice.paid_at = timezone.now()
        invoice.save(update_fields=["status", "paid_by", "paid_at"])

        from .models import PlatformPaymentTransaction

        PlatformPaymentTransaction.objects.create(
            invoice=invoice,
            company=invoice.company,
            amount_rial=invoice.amount_rial,
            provider=PlatformPaymentTransaction.Provider.MANUAL,
            status=PlatformPaymentTransaction.Status.VERIFIED,
            verified_at=timezone.now(),
        )

        if invoice.invoice_type == PlatformBillingInvoice.InvoiceType.SMS_RECHARGE:
            SMSCreditService.credit_wallet(
                company=invoice.company,
                amount_rial=invoice.amount_rial,
                invoice=invoice,
                created_by=paid_by,
            )

        _emit_platform_payment_success_admin_event(invoice, paid_by)

def _emit_platform_payment_success_admin_event(invoice, actor=None):
    # Emit platform-paid payment success event for company admins.
    if invoice is None or not getattr(invoice, "id", None):
        return None

    try:
        from apps.notifications.event_catalog import EventKey
        from apps.notifications.services_events import NotificationEventService

        company = getattr(invoice, "company", None)
        company_name = (
            getattr(company, "name", "")
            or getattr(company, "title", "")
            or "شرکت"
        )

        return NotificationEventService.emit(
            event_key=EventKey.PLATFORM_PAYMENT_SUCCESS_ADMIN,
            company=company,
            actor=actor,
            target=invoice,
            payload={
                "company_name": company_name,
                "platform_invoice_id": getattr(invoice, "id", None),
                "amount_rial": getattr(invoice, "amount_rial", 0),
                "invoice_type": str(getattr(invoice, "invoice_type", "")),
            },
            dedup_key=f"platform_payment_success_admin:platform_invoice:{invoice.id}",
        )
    except Exception:
        return None
