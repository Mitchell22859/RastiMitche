# چک‌لیست امنیتی استقرار — رستی‌سرویس

## ۱. متغیرهای محیطی ضروری

| متغیر | توضیح | مثال |
|--------|-------|------|
| `DJANGO_SETTINGS_MODULE` | ماژول تنظیمات | `config.settings.production` |
| `DJANGO_SECRET_KEY` | کلید رمزنگاری Django — یکتا و تصادفی | `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"` |
| `DJANGO_ALLOWED_HOSTS` | دامنه‌های مجاز (comma-separated) | `rastiservice.ir,www.rastiservice.ir` |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | دامنه‌ها با پروتکل | `https://rastiservice.ir,https://www.rastiservice.ir` |
| `DB_NAME` / `DATABASE_URL` | اتصال دیتابیس | — |
| `DB_USER` | کاربر دیتابیس | — |
| `DB_PASSWORD` | رمز دیتابیس | — |
| `DJANGO_SECURE_SSL_REDIRECT` | ریدایرکت HTTP→HTTPS | `True` |
| `DJANGO_SECURE_HSTS_SECONDS` | عمر HSTS | `31536000` (۱ سال) |
| `PAYMENT_EXPIRATION_MINUTES` | timeout پرداخت آنلاین | `30` |

---

## ۲. اجرای بررسی امنیتی Django

```bash
DJANGO_SETTINGS_MODULE=config.settings.production \
DJANGO_SECRET_KEY="your-secret-key" \
DJANGO_ALLOWED_HOSTS="yourdomain.com" \
DJANGO_CSRF_TRUSTED_ORIGINS="https://yourdomain.com" \
python manage.py check --deploy
```

تمام هشدارهای security باید رفع شوند.

---

## ۳. چک‌لیست DEBUG و اطلاعات حساس

- [ ] `DEBUG=False` در production
- [ ] `SECRET_KEY` تصادفی و یکتا (≥50 کاراکتر)
- [ ] `SECRET_KEY` هرگز در کد commit نشده
- [ ] `.env` در `.gitignore` قرار دارد
- [ ] هیچ رمز/کلید واقعی در repo وجود ندارد

---

## ۴. چک‌لیست ALLOWED_HOSTS و CSRF

- [ ] `ALLOWED_HOSTS` فقط شامل دامنه‌های واقعی (نه `*`)
- [ ] `CSRF_TRUSTED_ORIGINS` شامل `https://yourdomain.com`
- [ ] اگر از subdomain استفاده می‌شود، همه در لیست هستند

---

## ۵. حفاظت فایل‌های KYC

- [ ] مسیر `/media/companies/kyc/` در Nginx به `internal` تبدیل شده
- [ ] دسترسی مستقیم به `https://domain.com/media/companies/kyc/...` → 404
- [ ] فقط Django views با بررسی سطح دسترسی فایل serve می‌کنند
- [ ] جزئیات کامل: `docs/KYC_DOCUMENT_SECURITY.md`

---

## ۶. HTTPS و Reverse Proxy

- [ ] HTTPS فعال (Let's Encrypt / Certbot)
- [ ] `SECURE_SSL_REDIRECT=True`
- [ ] `SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")`
- [ ] Nginx → `proxy_set_header X-Forwarded-Proto $scheme;`

---

## ۷. Cookie Security

- [ ] `SESSION_COOKIE_SECURE = True`
- [ ] `CSRF_COOKIE_SECURE = True`
- [ ] `SESSION_COOKIE_HTTPONLY = True`
- [ ] `SESSION_COOKIE_SAMESITE = "Lax"`

---

## ۸. HSTS

- [ ] `SECURE_HSTS_SECONDS = 31536000` (یک سال)
- [ ] `SECURE_HSTS_INCLUDE_SUBDOMAINS = True`
- [ ] `SECURE_HSTS_PRELOAD = True` (فقط بعد از تست کامل)
- [ ] قبل از فعال‌سازی HSTS، مطمئن شوید HTTPS کاملاً کار می‌کند

---

## ۹. Content Security

- [ ] `SECURE_CONTENT_TYPE_NOSNIFF = True`
- [ ] `X_FRAME_OPTIONS = "DENY"`
- [ ] `SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"`

---

## ۱۰. قبل از اتصال درگاه واقعی (PSP)

- [ ] تمام موارد بالا تکمیل شده
- [ ] KYC/Merchant Profile شرکت تأیید شده
- [ ] `CompanyPaymentEligibilityService.is_gateway_enabled()` → True
- [ ] Callback URL روی HTTPS است
- [ ] Signature verification برای PSP مورد نظر پیاده‌سازی شده
- [ ] Amount tampering check فعال (P8 merged)
- [ ] Payment expiration فعال (P8 merged)
- [ ] تست end-to-end با sandbox/mock PSP انجام شده
- [ ] Reconciliation plan آماده است

---

## ۱۱. Logging و Monitoring

- [ ] Log‌های Django security فعال (`WARNING` level)
- [ ] Log‌های payment failure ثبت می‌شوند
- [ ] Alert برای AMOUNT TAMPERING DETECTED تنظیم شده
- [ ] Log rotation تنظیم شده
- [ ] Uptime monitoring فعال (health endpoint: `/health/`)

---

## ۱۲. Backup

- [ ] دیتابیس PostgreSQL → daily backup
- [ ] Media files → periodic backup
- [ ] `.env` → secure backup (نه در repo)
- [ ] Restore test انجام شده

---

## ۱۳. Rollback Plan

- [ ] هر deploy → tagged git commit
- [ ] Migration rollback تست شده
- [ ] اگر PSP خراب شد → gateway disable از admin panel
- [ ] اگر ledger مشکل پیدا کرد → `backfill_financial_ledgers --dry-run`

---

## دستور شروع سریع Production

```bash
# Set environment
export DJANGO_SETTINGS_MODULE=config.settings.production
export DJANGO_SECRET_KEY="$(python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())')"
export DJANGO_ALLOWED_HOSTS="rastiservice.ir,www.rastiservice.ir"
export DJANGO_CSRF_TRUSTED_ORIGINS="https://rastiservice.ir,https://www.rastiservice.ir"
export DATABASE_URL="postgres://user:pass@localhost:5432/rasti_service"

# Run checks
python manage.py check --deploy
python manage.py migrate
python manage.py collectstatic --noinput

# Start (gunicorn example)
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 3
```
