# امنیت اسناد KYC — راهنمای استقرار

## خلاصه

اسناد KYC (کارت ملی، جواز کسب، آگهی روزنامه رسمی) اطلاعات هویتی حساس هستند و
**نباید هرگز مستقیماً از طریق URL عمومی قابل دسترس باشند.**

این پروژه از Django FileResponse با بررسی سطح دسترسی استفاده می‌کند.
در محیط production، باید مطمئن شوید که وب‌سرور (Nginx/Apache) فایل‌های media را
مستقیماً serve نمی‌کند.

---

## معماری فعلی

### مسیرهای محافظت‌شده

| مسیر | دسترسی | فایل |
|------|--------|------|
| `/<company_code>/admin/payment/merchant-profile/document/<field>/` | ادمین/اپراتور شرکت مالک | `apps/tenants/views_merchant_profile.py` |
| `/owner-platform/merchant-profiles/<id>/document/<field>/` | فقط مالک پلتفرم | `apps/platform_core/views_merchant_profile.py` |
| `/owner-platform/merchant-profile-change-requests/<id>/document/<field>/` | فقط مالک پلتفرم | `apps/platform_core/views_merchant_profile.py` |

### بررسی‌های امنیتی سمت سرور

1. **احراز هویت**: کاربر باید login باشد
2. **بررسی نقش**: `require_tenant_role("COMPANY_ADMIN", "COMPANY_STAFF")` یا `require_platform_owner`
3. **بررسی عضویت tenant**: کاربر باید به همان شرکت تعلق داشته باشد (`user.company_id == request.company.id`)
4. **اعتبارسنجی فیلد**: فقط نام‌های مجاز (`national_card_image`, `business_license_image`, `latest_official_newspaper_image`)
5. **فایل موجود نباشد**: HTTP 404 برمی‌گردد

### چه چیزی مانع path traversal می‌شود؟

- فیلد‌ها از طریق `getattr(profile, field_name)` خوانده می‌شوند (نه مسیر مستقیم)
- نام فیلد در `_DOCUMENT_FIELDS` whitelist بررسی می‌شود
- هیچ ورودی کاربر مستقیماً به filesystem path تبدیل نمی‌شود

---

## ⚠️ ریسک production

### مشکل
در `config/urls.py`:

```python
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```

این فقط در `DEBUG=True` فعال است. اما اگر Nginx/Apache به‌صورت مستقیم مسیر
`/media/` را serve کند، تمام فایل‌های KYC **بدون هیچ بررسی دسترسی** قابل دانلود خواهند بود.

---

## ✅ استراتژی‌های پیشنهادی برای production

### گزینه ۱: Nginx X-Accel-Redirect (توصیه‌شده)

Django به جای ارسال مستقیم فایل، یک header خاص ارسال می‌کند و Nginx فایل را serve می‌کند:

**Nginx config:**
```nginx
# Block direct access to KYC files
location /media/companies/kyc/ {
    internal;  # Only accessible via X-Accel-Redirect
    alias /path/to/project/media/companies/kyc/;
}

# Block direct access to change request files
location /media/companies/kyc/change_requests/ {
    internal;
    alias /path/to/project/media/companies/kyc/change_requests/;
}

# Other media files (logos, gallery) can remain public
location /media/ {
    alias /path/to/project/media/;
    # Exclude KYC paths (handled above as internal)
}
```

**Django view تغییر (اختیاری — برای عملکرد بهتر):**
```python
from django.http import HttpResponse

def serve_profile_document(request, field_name, **kwargs):
    # ... permission checks ...
    response = HttpResponse()
    response["X-Accel-Redirect"] = f"/media/{file_obj.name}"
    response["Content-Type"] = ""  # Let Nginx detect
    return response
```

### گزینه ۲: Object Storage با Signed URLs

اگر از S3/MinIO/R2 استفاده می‌کنید:

1. فایل‌ها در bucket خصوصی ذخیره شوند
2. Django یک signed URL با عمر کوتاه (۵ دقیقه) تولید کند
3. کاربر به signed URL redirect شود

```python
import boto3
from botocore.config import Config

def generate_signed_url(file_key, expires_in=300):
    s3 = boto3.client("s3", config=Config(signature_version="s3v4"))
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": "rasti-kyc-private", "Key": file_key},
        ExpiresIn=expires_in,
    )
```

### گزینه ۳: حداقلی — Block مستقیم در Nginx

اگر Django FileResponse کافی است (ترافیک کم):

```nginx
# Block ALL direct media access to KYC folders
location ~* ^/media/companies/kyc/ {
    deny all;
    return 404;
}
```

---

## 🚫 چه کاری نباید انجام شود

| ❌ نادرست | ✅ درست |
|-----------|---------|
| `<img src="{{ profile.national_card_image.url }}">` | `<a href="/company/admin/.../document/national_card_image/">مشاهده</a>` |
| `MEDIA_URL` را public serve کردن برای KYC | `internal` location در Nginx |
| نمایش شبا/کارت بانکی کامل در readonly | استفاده از `shaba_masked` / `bank_card_number_masked` |
| ذخیره KYC در public bucket S3 | Private bucket + signed URL |
| `DEBUG=True` در production | `DEBUG=False` + Nginx internal |

---

## چک‌لیست استقرار

- [ ] `DEBUG=False` در `config/settings/production.py`
- [ ] Nginx مسیر `/media/companies/kyc/` را `internal` کرده
- [ ] دسترسی مستقیم به `https://domain.com/media/companies/kyc/...` تست شده → باید 404 برگرداند
- [ ] تست: ادمین شرکت A نمی‌تواند سند شرکت B را ببیند
- [ ] تست: کاربر بدون login نمی‌تواند سند را دانلود کند
- [ ] تست: تکنسین/مشتری نمی‌تواند سند KYC را ببیند
- [ ] حساسیت‌های بانکی (شبا، کارت، کد ملی) در صفحات readonly ماسک شده‌اند
- [ ] `SECURE_SSL_REDIRECT=True` فعال است
- [ ] `SESSION_COOKIE_SECURE=True` و `CSRF_COOKIE_SECURE=True` فعال هستند

---

## فایل‌های مرتبط

| فایل | نقش |
|------|-----|
| `apps/tenants/views_merchant_profile.py` | serve سند برای ادمین شرکت |
| `apps/platform_core/views_merchant_profile.py` | serve سند برای مالک پلتفرم |
| `apps/tenants/models.py` → `CompanyMerchantProfile` | مدل با فیلدهای FileField |
| `apps/accounts/permissions.py` → `require_tenant_role` | بررسی نقش + عضویت tenant |
| `config/urls.py` | DEBUG media serving (فقط dev) |
| `templates/tenants/merchant_profile.html` | رابط ادمین شرکت |
| `templates/platform_core/merchant_profile_detail.html` | رابط مالک پلتفرم |

---

## تاریخچه

| تاریخ | تغییر |
|-------|-------|
| P5 | ساخت CompanyMerchantProfile + document serving views |
| P7-HOTFIX | رفع cross-tenant access (require_tenant_role) |
| P9 | مستندسازی + تست‌های امنیتی + چک‌لیست deployment |
