# راهنمای Design Tokens — رستی‌سرویس

## اصل اول: از token استفاده کن، نه مقدار خام

```css
/* ❌ نادرست */
color: #2563eb;
border-radius: 12px;
box-shadow: 0 4px 6px rgba(0,0,0,0.1);

/* ✅ درست */
color: var(--color-primary);
border-radius: var(--radius-card);
box-shadow: var(--shadow-card);
```

---

## دسته‌بندی Token‌ها

### ۱. رنگ‌های اصلی (Primary)

| Token | مقدار | استفاده |
|-------|-------|---------|
| `--color-primary` | `#2563eb` (brand-600) | دکمه، لینک، CTA |
| `--color-primary-hover` | `#1d4ed8` (brand-700) | hover state |
| `--color-primary-light` | `#eff6ff` (brand-50) | پس‌زمینه روشن |
| `--color-primary-bg` | `#dbeafe` (brand-100) | badge/tag background |

### ۲. رنگ‌های وضعیت (Status)

| Token | مقدار | استفاده |
|-------|-------|---------|
| `--color-success` | `#16a34a` | موفق، تأیید |
| `--color-warning` | `#d97706` | هشدار، در انتظار |
| `--color-danger` | `#dc2626` | خطا، ناموفق |
| `--color-info` | `#2563eb` | اطلاعات |

هر status دارای variants هست:
- `--color-{status}-light` — پس‌زمینه alert
- `--color-{status}-border` — حاشیه alert
- `--color-{status}-dark` — متن داخل alert
- `--color-{status}-bg` — پس‌زمینه badge

### ۳. سطوح (Surfaces)

| Token | مقدار | استفاده |
|-------|-------|---------|
| `--color-bg` | `#f9fafb` | پس‌زمینه صفحه |
| `--color-surface` | `#ffffff` | کارت، modal |
| `--color-surface-soft` | `#f8fafc` | بخش‌های تو‌در‌تو |

### ۴. متن

| Token | مقدار | استفاده |
|-------|-------|---------|
| `--color-text` | slate-800 | متن اصلی |
| `--color-text-strong` | slate-900 | عنوان، bold |
| `--color-text-muted` | slate-500 | متن فرعی |
| `--color-text-faint` | slate-400 | placeholder |

### ۵. Radius

| Token | مقدار | استفاده |
|-------|-------|---------|
| `--radius-card` | `1rem` (14px) | گوشه کارت |
| `--radius-btn` | `0.5rem` (7px) | دکمه |
| `--radius-badge` | `9999px` | badge/pill |
| `--radius-input` | `0.375rem` (5.25px) | input |

### ۶. سایه

| Token | مقدار | استفاده |
|-------|-------|---------|
| `--shadow-card` | sm | کارت پیش‌فرض |
| `--shadow-card-hover` | md | hover state کارت |
| `--shadow-btn` | xs | دکمه |
| `--shadow-dropdown` | lg | منو/dropdown |

---

## قوانین استفاده

### ✅ مجاز

- استفاده از `var(--color-primary)` به جای `#2563eb`
- استفاده از `var(--radius-card)` به جای `16px` یا `1rem`
- استفاده از `var(--shadow-card)` به جای تعریف دستی shadow
- ایجاد component class جدید با token references

### ❌ غیرمجاز

- Hardcode رنگ hex در template inline style
- تعریف `border-radius: 12px` بدون token
- تعریف `box-shadow` custom بدون دلیل مستند
- استفاده از `--primary-color` (deprecated — فقط backward-compat)

---

## سلسله‌مراتب استفاده

1. **اول** → از semantic token استفاده کن (`--color-primary`, `--radius-card`)
2. **دوم** → از palette token استفاده کن (`--color-brand-600`, `--radius-xl`)
3. **هرگز** → مقدار خام hex/px مستقیم ننویس

---

## فایل‌ها

| فایل | نقش |
|------|-----|
| `static/css/tokens.css` | **تنها منبع حقیقت** — تمام متغیرها |
| `static/css/base.css` | Font-face + body reset |
| `static/css/components.css` | کلاس‌های قابل استفاده مجدد (btn, card, badge) |
| `static/css/layouts.css` | Sidebar + grid layout |
| `static/css/pages.css` | استایل خاص صفحات |
| `static/css/dashboard.css` | **Legacy** — در حال حذف تدریجی |

---

## نقشه آینده

- P19: inline styles → component classes (با token references)
- P20+: هر template بهبود‌یافته باید **فقط** از tokens استفاده کند
- `dashboard.css` به تدریج حذف می‌شود — classes به `components.css` منتقل شوند
