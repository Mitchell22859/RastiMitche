from django.db import models
from apps.tenants.models import Company
from apps.sms.models import SMSProvider, SMSOutbox
from apps.platform_core.models import CompanySMSWallet, GlobalSMSPricingSetting
from apps.sms.services import SMSSendService

company_code = "n54"

company = Company.objects.get(code=company_code)

# 1) کیف پول شرکت را صفر میکنیم تا اعتبار کافی نباشد
wallet, _ = CompanySMSWallet.objects.get_or_create(company=company)
wallet.balance_rial = 0
wallet.save(update_fields=["balance_rial", "updated_at"])

pricing = GlobalSMSPricingSetting.objects.first()
print("Pricing:", {
    "characters_per_sms": getattr(pricing, "characters_per_sms", None),
    "price_per_sms_rial": getattr(pricing, "price_per_sms_rial", None),
})
print("Wallet balance set to:", wallet.balance_rial)

# 2) ساخت/فعالسازی provider تستی Fake
provider_type_field = SMSProvider._meta.get_field("provider_type")
fake_value = None
for value, label in provider_type_field.choices:
    if "fake" in str(value).lower() or "fake" in str(label).lower():
        fake_value = value
        break

if fake_value is None:
    raise Exception("در SMSProvider.ProviderType گزینه Fake پیدا نشد. اول مدل SMSProvider را چک کن.")

def build_defaults_for_provider():
    defaults = {}
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
            defaults[field.name] = None
        elif isinstance(field, models.BooleanField):
            defaults[field.name] = True if field.name in ("is_active", "active", "enabled") else False
        elif isinstance(field, (models.CharField, models.TextField)):
            if "sender" in field.name.lower() or "number" in field.name.lower():
                defaults[field.name] = "1000"
            elif "name" in field.name.lower() or "title" in field.name.lower():
                defaults[field.name] = "Fake Test Provider"
            else:
                defaults[field.name] = "test"
        elif isinstance(field, (models.IntegerField, models.PositiveIntegerField, models.BigIntegerField)):
            defaults[field.name] = 0
    return defaults

provider, created = SMSProvider.objects.get_or_create(
    company=company,
    provider_type=fake_value,
    defaults=build_defaults_for_provider(),
)

# فعالسازی provider تستی اگر چنین فیلدهایی وجود داشته باشند
for attr in ("is_active", "active", "enabled"):
    if hasattr(provider, attr):
        setattr(provider, attr, True)

# اگر فیلد نام/شماره/کلید خالی باشد مقدار تستی میدهیم
for field in SMSProvider._meta.fields:
    if isinstance(field, (models.CharField, models.TextField)):
        current = getattr(provider, field.name, None)
        if current in ("", None):
            if "sender" in field.name.lower() or "number" in field.name.lower():
                setattr(provider, field.name, "1000")
            elif "name" in field.name.lower() or "title" in field.name.lower():
                setattr(provider, field.name, "Fake Test Provider")
            else:
                setattr(provider, field.name, "test")

provider.save()
print("Provider:", provider.id, provider.provider_type, "created=", created)

# 3) فقط یک پیامک queued را برای تست انتخاب میکنیم
sms = SMSOutbox.objects.filter(
    company=company,
    status=SMSOutbox.Status.QUEUED,
).order_by("-id").first()

if not sms:
    raise Exception("هیچ SMSOutbox با status=queued برای n54 پیدا نشد.")

print("Testing SMSOutbox id:", sms.id)
print("Before:", {
    "id": sms.id,
    "template_key": sms.template_key,
    "phone_number": sms.phone_number,
    "status": sms.status,
    "error_message": sms.error_message,
})

# 4) تلاش برای ارسال همان یک پیامک
# به خاطر wallet=0 باید قبل از ارسال واقعی fail شود
try:
    SMSSendService.send(sms=sms)
except TypeError:
    SMSSendService.send(sms)

sms.refresh_from_db()
wallet.refresh_from_db()

print("After:", {
    "id": sms.id,
    "template_key": sms.template_key,
    "phone_number": sms.phone_number,
    "status": sms.status,
    "error_message": sms.error_message,
})
print("Wallet after:", wallet.balance_rial)

print("Done. Open:")
print(f"http://127.0.0.1:8002/{company.code}/admin/sms/outbox/")
print(f"http://127.0.0.1:8002/{company.code}/admin/sms/outbox/{sms.id}/")
