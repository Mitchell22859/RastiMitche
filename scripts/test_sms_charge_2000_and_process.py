from django.db import transaction, models
from apps.tenants.models import Company
from apps.sms.models import SMSProvider, SMSOutbox
from apps.sms.services import SMSOutboxProcessorService
from apps.platform_core.models import CompanySMSWallet, CompanySMSTransaction, GlobalSMSPricingSetting

company_code = "n54"
charge_amount = 200000
process_limit = 20

company = Company.objects.get(code=company_code)

# 1) ساخت/فعالسازی provider تستی fake برای اینکه پیام واقعی ارسال نشود
provider_type_field = SMSProvider._meta.get_field("provider_type")
fake_value = None
for value, label in provider_type_field.choices:
    if "fake" in str(value).lower() or "fake" in str(label).lower():
        fake_value = value
        break

if fake_value is None:
    raise Exception("Provider type fake در مدل SMSProvider پیدا نشد.")

def provider_defaults():
    data = {}
    for field in SMSProvider._meta.fields:
        if field.primary_key or field.auto_created:
            continue
        if field.name in ("company", "provider_type"):
            continue
        if getattr(field, "auto_now", False) or getattr(field, "auto_now_add", False):
            continue
        if field.has_default():
            continue
        if field.null:
            data[field.name] = None
        elif isinstance(field, models.BooleanField):
            data[field.name] = True if field.name in ("is_active", "active", "enabled") else False
        elif isinstance(field, (models.CharField, models.TextField)):
            if "sender" in field.name.lower() or "number" in field.name.lower():
                data[field.name] = "1000"
            elif "name" in field.name.lower() or "title" in field.name.lower():
                data[field.name] = "Fake Test Provider"
            else:
                data[field.name] = "test"
        elif isinstance(field, (models.IntegerField, models.PositiveIntegerField, models.BigIntegerField)):
            data[field.name] = 0
    return data

provider, created = SMSProvider.objects.get_or_create(
    company=company,
    provider_type=fake_value,
    defaults=provider_defaults(),
)

for attr in ("is_active", "active", "enabled"):
    if hasattr(provider, attr):
        setattr(provider, attr, True)

for field in SMSProvider._meta.fields:
    if isinstance(field, (models.CharField, models.TextField)):
        value = getattr(provider, field.name, None)
        if value in ("", None):
            if "sender" in field.name.lower() or "number" in field.name.lower():
                setattr(provider, field.name, "1000")
            elif "name" in field.name.lower() or "title" in field.name.lower():
                setattr(provider, field.name, "Fake Test Provider")
            else:
                setattr(provider, field.name, "test")

provider.save()

# 2) شار کیف پول شرکت به مبلغ 2000 ریال
with transaction.atomic():
    wallet, _ = CompanySMSWallet.objects.select_for_update().get_or_create(company=company)
    before_balance = wallet.balance_rial
    wallet.balance_rial = wallet.balance_rial + charge_amount
    wallet.save(update_fields=["balance_rial", "updated_at"])

    CompanySMSTransaction.objects.create(
        company=company,
        wallet=wallet,
        transaction_type=CompanySMSTransaction.TransactionType.CREDIT,
        amount_rial=charge_amount,
        sms_parts=0,
        message_length=0,
        balance_after=wallet.balance_rial,
        description=f"شار تستی کیف پول پیامک به مبلغ {charge_amount} ریال",
    )

pricing = GlobalSMSPricingSetting.objects.first()

print("=== BEFORE PROCESS ===")
print("company:", company.code)
print("provider:", provider.provider_type, "id=", provider.id)
print("pricing:", {
    "characters_per_sms": getattr(pricing, "characters_per_sms", None),
    "price_per_sms_rial": getattr(pricing, "price_per_sms_rial", None),
})
print("wallet before charge:", before_balance)
print("wallet after charge:", wallet.balance_rial)
print("queued count:", SMSOutbox.objects.filter(company=company, status=SMSOutbox.Status.QUEUED).count())

# 3) پردازش پیامکهای queued
# اینجا dry_run=False است ولی چون provider=fake است پیام واقعی ارسال نمیشود.
results = SMSOutboxProcessorService.process(
    company=company,
    limit=process_limit,
    dry_run=False,
)

wallet.refresh_from_db()

print("=== PROCESS RESULT ===")
print(results)
print("wallet after process:", wallet.balance_rial)

print("=== LATEST SMS ===")
for row in SMSOutbox.objects.filter(company=company).order_by("-id").values(
    "id", "template_key", "phone_number", "status", "error_message"
)[:30]:
    print(row)

print("=== LATEST TRANSACTIONS ===")
for row in CompanySMSTransaction.objects.filter(company=company).order_by("-id").values(
    "id", "transaction_type", "amount_rial", "sms_parts", "message_length", "balance_after", "description"
)[:30]:
    print(row)

print("Open:")
print(f"http://127.0.0.1:8002/{company.code}/admin/sms/outbox/")
