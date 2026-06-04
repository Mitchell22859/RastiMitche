import re
from django.utils import timezone

from apps.tenants.models import Company
from apps.invoices.models import Invoice
from apps.reports.models import DiscountCode
from apps.sms.models import SMSOutbox

try:
    from apps.sms.services import normalize_sms_phone_number
except Exception:
    normalize_sms_phone_number = lambda x: x


COMPANY_CODE = "n54"
INVOICE_ID = 3
PHONE = "09177305910"


def extract_discount_code(message: str):
    message = message or ""

    patterns = [
        r"کد\s*تخفیف\s*شما\s*[:：]\s*([A-Za-z0-9]{4,12})",
        r"کد\s*تخفیف\s*[:：]\s*([A-Za-z0-9]{4,12})",
        r"discount\s*code\s*[:：]\s*([A-Za-z0-9]{4,12})",
    ]

    for pattern in patterns:
        m = re.search(pattern, message, re.IGNORECASE)
        if m:
            return m.group(1)

    for line in message.splitlines():
        if "کد" in line or "code" in line.lower():
            m = re.search(r"\b[A-Za-z0-9]{4,12}\b", line)
            if m:
                return m.group(0)

    return ""


company = Company.objects.get(code=COMPANY_CODE)

invoice_phone = ""
try:
    invoice = Invoice.objects.get(company=company, id=INVOICE_ID)
    invoice_phone = getattr(invoice, "display_customer_phone", "") or ""
    print("Invoice:", invoice.invoice_number)
    print("Invoice phone:", invoice_phone)
except Exception as exc:
    invoice = None
    print("Invoice not loaded:", exc)

phone = invoice_phone or PHONE
normalized_phone = normalize_sms_phone_number(phone) or phone

phone_variants = {phone, normalized_phone, PHONE}
phone_variants = {p for p in phone_variants if p}

print("Search phones:", phone_variants)
print("-" * 70)

codes = DiscountCode.objects.filter(
    company=company,
    phone_number__in=phone_variants,
).order_by("-created_at")

if not codes.exists():
    print("هیچ DiscountCode مستقیمی برای این شماره پیدا نشد. جستجوی گستردهتر روی Outbox انجام میشود...")
else:
    print("DiscountCode count:", codes.count())

for dc in codes[:20]:
    sms = None
    if dc.sms_outbox_id:
        sms = SMSOutbox.objects.filter(company=company, id=dc.sms_outbox_id).first()

    raw_code = extract_discount_code(getattr(sms, "message", "") or "")

    print("DiscountCode ID:", dc.id)
    print("Campaign:", dc.campaign_id)
    print("Customer:", dc.customer_name_snapshot)
    print("Phone:", dc.phone_number)
    print("Status:", dc.status)
    print("Masked:", dc.code_masked)
    print("Percent:", dc.percent)
    print("Max discount rial:", dc.max_discount_rial)
    print("Expires:", timezone.localtime(dc.expires_at) if dc.expires_at else "-")
    print("SMSOutbox ID:", dc.sms_outbox_id)
    print("RAW CODE FOR LOCAL TEST:", raw_code or "در متن SMSOutbox پیدا نشد")
    print("-" * 70)

sms_qs = SMSOutbox.objects.filter(
    company=company,
    template_key="discount_code_customer",
    phone_number__in=phone_variants,
).order_by("-created_at")

print("Discount SMSOutbox count:", sms_qs.count())

for sms in sms_qs[:10]:
    raw_code = extract_discount_code(sms.message)
    print("SMS ID:", sms.id)
    print("Phone:", sms.phone_number)
    print("Status:", sms.status)
    print("Created:", timezone.localtime(sms.created_at))
    print("RAW CODE FOR LOCAL TEST:", raw_code or "پیدا نشد")
    print("Message:")
    print(sms.message)
    print("-" * 70)
