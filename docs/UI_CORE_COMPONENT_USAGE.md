# راهنمای استفاده از Component‌های UI Core

## اصل اول: از class مرکزی استفاده کن

```html
<!-- ❌ نادرست -->
<div style="background:white;border-radius:1rem;box-shadow:0 1px 3px...;padding:1.25rem;">

<!-- ✅ درست -->
<div class="card">
```

---

## کارت‌ها (Cards)

```html
<div class="card">
  <div class="card-header">
    <span class="card-header-title">عنوان</span>
  </div>
  <!-- محتوا -->
</div>
```

| Class | استفاده |
|-------|---------|
| `.card` | کارت اصلی — سطح سفید، radius-card، shadow-card |
| `.card-header` | عنوان بالای کارت + separator |
| `.card-header-title` | متن عنوان کارت |
| `.card-body` | محتوای اصلی |
| `.card-footer` | عمل/دکمه پایین |
| `.card-compact` | padding کمتر |

---

## دکمه‌ها (Buttons)

```html
<button class="btn btn-primary">ثبت</button>
<a href="..." class="btn btn-outline">بازگشت</a>
<button class="btn btn-danger btn-sm">حذف</button>
```

| Class | ظاهر |
|-------|------|
| `.btn-primary` | آبی solid / CTA |
| `.btn-secondary` | خاکستری/surface |
| `.btn-outline` | حاشیه + transparent |
| `.btn-danger` | قرمز |
| `.btn-success` | سبز |
| `.btn-ghost` | بدون حاشیه |
| `.btn-sm` | کوچک |
| `.btn-lg` | بزرگ |

---

## Badge / Status Pill

```html
<span class="badge badge-success">پرداخت‌شده</span>
<span class="badge badge-warning">در انتظار</span>
<span class="badge badge-danger">ناموفق</span>
<span class="badge badge-info">جدید</span>
<span class="badge badge-neutral">لغو</span>
```

---

## Alert‌ها

```html
<div class="alert alert-success" dir="rtl">
  <div class="alert-body">عملیات با موفقیت انجام شد.</div>
</div>

<div class="alert alert-warning" dir="rtl">
  <div class="alert-body">
    <div class="alert-title">هشدار</div>
    توضیحات هشدار...
  </div>
</div>
```

| Class | رنگ |
|-------|------|
| `.alert-success` | سبز |
| `.alert-warning` | زرد/amber |
| `.alert-error` / `.alert-danger` | قرمز |
| `.alert-info` | آبی |

---

## Empty State (حالت خالی)

```html
<div class="card empty-state" dir="rtl">
  <div class="empty-state-icon">📋</div>
  <p class="empty-state-title">هیچ داده‌ای وجود ندارد</p>
  <p class="empty-state-description">توضیح مختصر...</p>
</div>
```

### حالت سالم (Healthy)

```html
<div class="card empty-state empty-state-healthy" dir="rtl">
  <div class="empty-state-icon">✓</div>
  <p class="empty-state-title">همه چیز سالم است</p>
  <p class="empty-state-description">توضیح...</p>
</div>
```

---

## Stat Card

```html
<div class="stat-card">
  <div class="stat-card-icon blue">📊</div>
  <span class="stat-card-value">42</span>
  <div class="stat-card-label">سفارش امروز</div>
</div>
```

رنگ‌ها: `blue`, `green`, `amber`, `red`, `purple`, `indigo`

---

## جدول‌ها (Tables)

```html
<div class="card" style="padding:0;overflow:hidden;">
  <div class="table-wrapper">
    <table class="data-table">
      <thead>...</thead>
      <tbody>...</tbody>
    </table>
  </div>
</div>
```

---

## قوانین

- ❌ از `style="..."` برای رنگ، radius، shadow استفاده نکنید
- ❌ از hex color خام استفاده نکنید
- ❌ از `border-radius: 12px` بدون token استفاده نکنید
- ✅ از `class="card"` استفاده کنید
- ✅ از `class="btn btn-primary"` استفاده کنید
- ✅ از `class="badge badge-success"` استفاده کنید
- ✅ از `class="alert alert-warning"` استفاده کنید
- ✅ از `class="empty-state empty-state-healthy"` استفاده کنید
