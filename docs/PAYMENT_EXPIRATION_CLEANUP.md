# پاکسازی پرداخت‌های منقضی — راهنمای عملیاتی

## خلاصه

پرداخت‌های آنلاین (gateway) که به وضعیت `PENDING` یا `INITIATED` رفته‌اند اما هرگز callback
دریافت نکرده‌اند، باید پس از مدت معینی به عنوان منقضی (FAILED) علامت‌گذاری شوند.

---

## دستور مدیریتی

```bash
# نمایش بدون تغییر (dry-run)
python manage.py expire_pending_payments --dry-run

# اجرای واقعی
python manage.py expire_pending_payments

# با threshold سفارشی (مثلاً 60 دقیقه)
python manage.py expire_pending_payments --minutes 60

# محدود به یک شرکت
python manage.py expire_pending_payments --company-code n54

# محدودیت تعداد
python manage.py expire_pending_payments --limit 500
```

---

## برنامه‌ریزی cron پیشنهادی

```cron
# هر ۱۵ دقیقه پرداخت‌های منقضی را پاکسازی کن
*/15 * * * * cd /path/to/project && python manage.py expire_pending_payments >> /var/log/rasti/expire_payments.log 2>&1
```

---

## رفتار

| شرایط | نتیجه |
|--------|-------|
| Payment: PENDING + gateway + age > threshold | → FAILED |
| Payment: INITIATED + gateway + age > threshold | → FAILED |
| Payment: PAID | بدون تغییر |
| Payment: FAILED / CANCELLED | بدون تغییر |
| Payment بدون gateway (cash/manual) | بدون تغییر |
| Payment جدیدتر از threshold | بدون تغییر |
| Invoice | وضعیت تغییر نمی‌کند |
| Technician ledger | هیچ entry ساخته نمی‌شود |
| Platform fee ledger | هیچ entry ساخته نمی‌شود |

---

## تنظیمات

| متغیر | محل | مقدار پیش‌فرض |
|--------|-----|-------------|
| `PAYMENT_EXPIRATION_MINUTES` | settings / env | 30 دقیقه |

---

## چه کاری انجام نمی‌دهد

- ❌ Refund یا بازگشت وجه
- ❌ تغییر وضعیت فاکتور
- ❌ ایجاد ردیف لجر
- ❌ تماس با درگاه پرداخت
- ❌ تغییر پرداخت‌های نقدی/دستی

---

## ارتباط با reconciliation

این دستور **جایگزین reconciliation نیست.**

اگر یک پرداخت واقعاً در سمت PSP موفق بوده اما callback نرسیده:
1. ابتدا باید reconciliation با PSP انجام شود
2. اگر PSP تأیید کرد: verify دستی
3. اگر PSP تأیید نکرد: expire ایمن است

**توصیه:** قبل از اجرای expire، reconciliation report PSP را بررسی کنید.

---

## Metadata ذخیره‌شده

پس از expire، در `payment.metadata`:
```json
{
  "expired_by_cleanup": true,
  "expired_at": "2026-06-06T10:30:00+03:30",
  "expiration_threshold_minutes": 30
}
```

---

## Idempotency

اجرای مجدد دستور روی payment‌هایی که قبلاً FAILED شده‌اند هیچ تغییری ایجاد نمی‌کند.
