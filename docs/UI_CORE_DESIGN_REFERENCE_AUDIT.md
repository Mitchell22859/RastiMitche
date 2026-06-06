# ممیزی مرجع طراحی UI Core — رستی‌سرویس (P17)

---

## ۱. خلاصه جهت بصری تأییدشده

سبک هدف: **رابط فارسی مدرن SaaS** — حرفه‌ای، پریمیوم، نه admin-panel قدیمی.

| معیار | جهت |
|-------|------|
| احساس کلی | تمیز، مدرن، فضادار، سایه‌های نرم |
| پس‌زمینه | بسیار روشن (سفید / خاکستری-آبی ملایم) |
| رنگ اصلی | آبی/ایندیگو (`--color-brand-600`) |
| Success | سبز زمردی |
| Warning | کهربایی |
| Danger | رز/قرمز |
| متن اصلی | اسلیت تیره (`--color-slate-800/900`) |
| حاشیه‌ها | خاکستری-آبی نرم (`--color-slate-200`) |
| گوشه‌ها | گرد (radius بزرگ) |
| سایه | نرم (`box-shadow: 0 1px 3px...`) |
| فونت | Vazirmatn — فارسی RTL |
| اعداد | خوانا، monospace-safe در کارت‌ها و جداول |
| دکمه‌ها | Gradient یا solid آبی، شعاع ثابت، hover state |
| Badge | Pill rounded، رنگ‌های status ثابت |
| جدول | Container گرد، header روشن، فاصله مناسب |
| فرم | Input‌ها با radius، label واضح، hint text |
| Empty state | دوستانه، توضیح‌دار، آیکون |
| Alert | رنگ‌بندی ثابت، read-only واضح |

---

## ۲. فهرست فایل‌های CSS موجود

| فایل | خطوط | نقش |
|------|-------|-----|
| `static/css/tokens.css` | 221 | متغیرهای CSS (رنگ، فاصله، radius، فونت) |
| `static/css/base.css` | 377 | Reset + عناصر پایه (body, a, headings) |
| `static/css/components.css` | 1047 | کامپوننت‌های قابل‌استفاده مجدد (btn, card, badge, table, form, alert) |
| `static/css/layouts.css` | 654 | Grid/sidebar/main layout |
| `static/css/pages.css` | 1224 | استایل‌های خاص صفحات (financial, invoice, login) |
| `static/css/dashboard.css` | 1392 | استایل‌های قدیمی‌تر dashboard (overlap با components) |
| `static/css/responsive.css` | 327 | Media queries |
| `static/css/jalali_datepicker.css` | 73 | Datepicker فارسی |
| `static/css/app.css` | 9 | Import aggregator |
| **مجموع** | **5324** | |

**نکته:** `dashboard.css` و `components.css` overlap دارند. `components.css` بعد از `dashboard.css` load می‌شود و اولویت دارد.

---

## ۳. نقشه ارث‌بری Template

| حوزه | Base Template | تعداد |
|------|--------------|-------|
| ادمین شرکت (فاکتور، سفارش، تکنسین، تنظیمات) | `base_dashboard.html` | ~67 |
| مالک پلتفرم (شرکت‌ها، KYC، درگاه، گزارش) | `layouts/dashboard.html` | ~57 |
| صفحات عمومی (landing, request, home) | `base.html` / `layouts/public.html` | ~19+8 |
| احراز هویت (login, password reset) | `layouts/auth.html` | ~7 |
| پنل تکنسین | `layouts/technician.html` | ~4 |

**مشکل:** دو base layout مجزا (`base_dashboard.html` و `layouts/dashboard.html`) → ناسازگاری احتمالی بین tenant و platform.

---

## ۴. گزارش ناسازگاری UI

### ۴.۱ آمار کلی

| متریک | تعداد |
|--------|-------|
| **Inline style** در templates | **1,322** |
| Hardcoded hex color | **466** |
| Inline style در financial reports | 120 |
| Inline style در payments | 98 |
| Inline style در payouts | 169 |
| Inline style در platform_core | 92 |

### ۴.۲ مشکلات اصلی

| مشکل | شدت | مثال |
|------|------|------|
| **Inline styles فراوان** | High | `style="color:var(--color-slate-500);margin:.35rem..."` — در تقریباً تمام templates |
| **Hardcoded hex colors** | Medium | `color:#7c3aed`, `background:#f8fafc` → باید از tokens استفاده شود |
| **Two competing dashboard CSS** | Medium | `dashboard.css` vs `components.css` → overlap/confusion |
| **Platform templates use Tailwind classes** | Medium | `class="px-5 py-3 text-sm..."` → mix Tailwind + custom CSS |
| **Tenant templates use component CSS** | Low | `class="btn btn-primary"` → consistent |
| **Inconsistent card styles** | Medium | برخی `class="card"` + inline، برخی فقط inline |
| **Financial report tables** | Low | از `class="data-table"` استفاده می‌کنند (خوب) |
| **Payment operations templates** | Medium | Mix Tailwind (platform) + component CSS (tenant) |
| **Empty states** | Low | الان بهبود یافته (P16) اما style هنوز inline |

### ۴.۳ صفحات با بیشترین inline style

1. `payouts/technician_ledger.html` (~50 inline styles)
2. `tenants/financial_reports/summary.html` (~40)
3. `tenants/admin_invoice_detail.html` (~35)
4. `payouts/split_snapshot_list.html` (~30)
5. `platform_core/merchant_profile_detail.html` (~25)

---

## ۵. تحلیل خلأ کامپوننت‌ها

| کامپوننت | در `components.css`? | در templates? | خلأ |
|----------|---------------------|---------------|------|
| `.btn` variants | ✅ کامل | ✅ استفاده‌شده | ✓ OK |
| `.card` | ✅ | ✅ اما + inline | ⚠️ inline اضافی |
| `.badge` variants | ✅ | ✅ | ✓ OK |
| `.stat-card` | ✅ | ✅ (dashboard) | ⚠️ financial reports از component استفاده نمی‌کنند |
| `.data-table` | ✅ | ✅ | ✓ OK |
| `.form-control/.form-group` | ✅ | ⚠️ partial | ⚠️ برخی فرم‌ها کلاس ندارند |
| `.alert` variants | ✅ | ✅ | ✓ OK |
| `.empty-state` | ⚠️ partial | ⚠️ inline-heavy | ❌ نیاز به class ثابت |
| `.balance-insight` | ✅ (pages.css) | ✅ | ✓ OK |
| `.fin-subnav` | ✅ (pages.css) | ✅ | ✓ OK |
| `.page-header` | ✅ | ✅ | ✓ OK |
| Modal | ❌ ندارد | ❌ استفاده نشده | — |
| Breadcrumb | ✅ (partial) | ⚠️ فقط یک template | ❌ نیاز به گسترش |
| Responsive sidebar | ⚠️ | ⚠️ | ⚠️ نیاز به بررسی |

---

## ۶. رتبه‌بندی ریسک تغییر UI

### High Risk (تغییر UI ممکن است منطق مالی/امنیتی را خراب کند)

| صفحه | دلیل ریسک |
|------|-----------|
| `admin_invoice_detail.html` | دکمه‌های mark_paid + CSRF + confirm + محاسبه wage |
| `technician_settlement.html` | فرم POST + idempotency token + direction radio |
| `merchant_profile.html` | File upload + KYC masking + editable/readonly switch |
| `platform_core/merchant_profile_detail.html` | approve/reject POST + masked fields |
| `payments/operations_*.html` | Alert logic بر اساس context variable |

### Medium Risk

| صفحه | دلیل |
|------|------|
| `financial_reports/summary.html` | KPI cards + conditional colors |
| `technician_ledger.html` | جدول مالی + balance display |
| `split_snapshot_list.html` | فیلترها + جدول |
| `admin_payment_gateway.html` | فرم POST + eligibility display |

### Low Risk

| صفحه | دلیل |
|------|------|
| `dashboard/home.html` | فقط stat cards + quick links |
| `platform_core/dashboard.html` | مشابه |
| `includes/nav_admin.html` | فقط لینک‌ها |
| `includes/nav_platform.html` | فقط لینک‌ها |
| `financial_reports/_nav.html` | subnav ساده |

---

## ۷. نقشه راه پیشنهادی فازبندی‌شده

| فاز | نام | scope | ریسک |
|------|------|-------|------|
| **P18** | UI Tokens Upgrade | به‌روزرسانی tokens.css + حذف overlap dashboard.css/components.css | Low |
| **P19** | Shared Component Normalization | تبدیل inline styles به class در ≤10 template کم‌ریسک | Low |
| **P20** | Company Admin Dashboard Polish | `dashboard/home.html` + stat cards | Low |
| **P21** | Financial Reports Polish | 6 report template → component classes | Medium |
| **P22** | Invoice/Payment UI Polish | `admin_invoice_detail` + payment forms | **High** |
| **P23** | Technician Ledger & Settlement Polish | ledger table + settlement form | **High** |
| **P24** | Merchant/KYC UI Polish | KYC form + readonly masking | **High** |
| **P25** | Platform Owner UI Polish | platform templates → consistent with tenant | Medium |
| **P26** | Login/Account/Public Pages | auth templates + public landing | Low |
| **P27** | Responsive/Mobile Pass | media queries + sidebar mobile | Medium |
| **P28** | Visual Regression Checklist | screenshot-based test + manual QA doc | Low |

---

## ۸. قوانین عدم شکست (Do-Not-Break Rules)

هر فاز UI آینده **باید** این قوانین را رعایت کند:

- ❌ هیچ تغییری در فرمول‌های مالی (settlement, wage, fee)
- ❌ هیچ تغییری در منطق status پرداخت
- ❌ هیچ تغییری در permissions/decorators
- ❌ هیچ نشت KYC/media (file.url → protected route)
- ❌ هیچ نمایش raw شبا/کارت/کد ملی در readonly
- ❌ هیچ import از React/Tailwind CDN/npm bundler
- ❌ هیچ migration مگر واقعاً لازم باشد
- ✅ تمام ۱۴۲+ تست موجود باید pass شوند
- ✅ `manage.py check` باید بدون خطا باشد
- ✅ `manage.py validate_templates` بدون خطا
- ✅ CSRF token در تمام POST فرم‌ها حفظ شود
- ✅ `dir="rtl"` در تمام container‌ها حفظ شود

---

## ۹. اولین فاز کدنویسی پیشنهادی پس از این ممیزی

**P18: UI Tokens Upgrade** (کم‌ریسک‌ترین)

محتوا:
1. مرتب‌سازی `tokens.css` — اضافه کردن متغیرهای spacing/shadow/transition اگر ناقص
2. شناسایی و حذف duplicate definitions بین `dashboard.css` و `components.css`
3. اضافه کردن `.empty-state` class به `components.css` (جایگزین inline)
4. بدون تغییر template — فقط CSS consolidation
5. اجرای تمام تست‌ها

**دلیل:** هیچ template تغییر نمی‌کند → صفر ریسک شکست منطق → آماده‌سازی برای فازهای بعدی.

---

## ۱۰. خلاصه آمار

| متریک | مقدار |
|--------|-------|
| فایل CSS | 9 (5,324 خط) |
| Templates با inline style | ~100+ |
| Hardcoded hex colors | 466 مورد |
| Base templates | 5 نوع |
| تست‌های موجود | 142+ |
| Migrations لازم | 0 |
| Production code تغییر | 0 |
