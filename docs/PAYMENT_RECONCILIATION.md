# تطبیق پرداخت‌ها (Payment Reconciliation) — راهنمای عملیاتی

## هدف

مقایسه رکوردهای داخلی Payment با گزارش تسویه PSP خارجی برای شناسایی مغایرت‌ها.

---

## ⚠️ اصل مهم

**این ابزار فقط AUDIT-ONLY است.**

- ❌ هرگز invoice را PAID نمی‌کند
- ❌ هرگز ledger entry ایجاد نمی‌کند
- ❌ هرگز platform fee ثبت نمی‌کند
- ❌ هرگز payment status را تغییر نمی‌دهد
- ✅ فقط گزارش مغایرت‌ها را نمایش می‌دهد

---

## فرمت CSV ورودی

### ستون‌های اجباری

| ستون | نوع | توضیح |
|------|------|-------|
| `provider_reference` | string | شناسه مرجع PSP (Authority / reference_id) |
| `amount` | integer | مبلغ به ریال |
| `status` | string | وضعیت: paid, failed, pending, refunded |

### ستون‌های اختیاری

| ستون | نوع | توضیح |
|------|------|-------|
| `paid_at` | string | تاریخ پرداخت ISO |
| `raw_id` | string | شناسه داخلی PSP |

### مثال

```csv
provider_reference,amount,status,paid_at
SUCCESS-abc123,5000000,paid,2026-06-01T10:30:00
SUCCESS-def456,3000000,paid,2026-06-01T11:00:00
FAIL-xyz789,2000000,failed,
```

---

## دستور اجرا

```bash
# Audit-only (همیشه)
python manage.py reconcile_payments --file report.csv

# محدود به یک شرکت
python manage.py reconcile_payments --file report.csv --company-code n54

# محدود به نوع درگاه
python manage.py reconcile_payments --file report.csv --gateway-type zarinpal
```

---

## خروجی نمونه

```
AUDIT-ONLY MODE — no data will be modified.

  Parsed 25 valid row(s) from CSV.

==================================================
  RECONCILIATION SUMMARY
==================================================
  Provider rows scanned:     25
  Matched:                   22
  Missing in internal DB:    1
  Missing in provider:       2
  Amount mismatch:           0
  Status mismatch:           1
  Duplicate references:      0
  Errors:                    0
==================================================

  3 issue(s) found:

  [missing_in_internal] ref=UNKNOWN-999 ...
  [missing_in_provider] ref=SUCCESS-old1 ...
  [status_mismatch_provider_paid] ref=SUCCESS-abc ...

  ACTION REQUIRED: Review issues above.
```

---

## مغایرت‌ها و اقدام پیشنهادی

| کد مغایرت | معنی | اقدام |
|-----------|------|-------|
| `missing_in_internal` | PSP یک پرداخت گزارش کرده اما در سیستم وجود ندارد | بررسی دستی — ممکن است مربوط به شرکت دیگر باشد |
| `missing_in_provider` | سیستم یک پرداخت PENDING/PAID دارد اما PSP گزارش نکرده | بررسی با PSP — ممکن است expire شده باشد |
| `amount_mismatch` | مبلغ PSP با مبلغ داخلی متفاوت است | 🔴 بحرانی — احتمال tampering یا خطای PSP |
| `status_mismatch_provider_paid` | PSP می‌گوید PAID اما داخلی PENDING/FAILED | بررسی دستی — ممکن است callback نرسیده باشد |
| `status_mismatch_provider_failed` | PSP می‌گوید FAILED اما داخلی هنوز PENDING | expire کردن ایمن است |
| `duplicate_provider_reference` | یک reference در گزارش PSP تکرار شده | بررسی با PSP |

---

## ارتباط با فازهای قبلی

| فاز | ارتباط |
|-----|--------|
| P8 (Callback Safety) | اگر callback رسید اما amount_mismatch داشت → FAILED شده |
| P11 (Expiration Cleanup) | اگر payment expire شده → قبلاً FAILED شده |
| P12 (Reconciliation) | مغایرت‌های باقی‌مانده شناسایی می‌شوند |

---

## چک‌لیست بررسی دستی

اگر reconciliation مغایرت پیدا کرد:

1. [ ] `status_mismatch_provider_paid` → با PSP تماس بگیرید و وضعیت واقعی را تأیید کنید
2. [ ] اگر PSP تأیید کرد paid است → از admin panel manually verify کنید
3. [ ] `amount_mismatch` → هرگز auto-settle نکنید — بررسی امنیتی لازم است
4. [ ] `missing_in_internal` → ممکن است test payment یا شرکت دیگر باشد
5. [ ] `missing_in_provider` → اگر PENDING → expire کنید، اگر PAID → مشکل PSP

---

## نکته PSP آینده

هر PSP adapter آینده (ZarinPal, Zibal, IDPay) باید:
1. یک تابع `export_settlement_csv()` یا `fetch_settlement_report()` پیاده‌سازی کند
2. خروجی را به فرمت `ProviderReportRow` تبدیل کند
3. سپس `PaymentReconciliationService.reconcile()` را فراخوانی کند

تا آن زمان، CSV خروجی PSP dashboard به صورت دستی import می‌شود.
