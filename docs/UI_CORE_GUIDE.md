# UI Core Guide — Rasti Service

This document defines how to build pages consistently using the Design System
CSS files. Read this before writing any new template or CSS.

---

## CSS Loading Order

```html
tokens.css      ← CSS custom properties only (:root). No selectors.
base.css        ← html, body, headings, links, form reset, RTL defaults, helpers
dashboard.css   ← Legacy Tailwind-equivalent utility classes (do not remove)
components.css  ← Reusable UI components: buttons, cards, forms, tables, badges, etc.
layouts.css     ← Shell layouts: dashboard, sidebar, topbar, auth, public, tech, error, invoice
pages.css       ← Page-section helpers: hero, features, pricing, technician cards, etc.
responsive.css  ← Media queries only — overrides for all of the above
```

**Rule:** Never put `@media` queries in `tokens.css`, `base.css`, or `components.css`.
All responsive overrides belong in `responsive.css`.

---

## Design Token Usage

All visual values come from `tokens.css`. Use tokens everywhere — never hardcode
a color, spacing, radius, shadow, or transition value in a component or layout.

```css
/* Correct */
color: var(--color-slate-700);
padding: var(--space-4);
border-radius: var(--radius-lg);
box-shadow: var(--shadow-sm);
transition: var(--transition-base);

/* Wrong */
color: #374151;
padding: 16px;
border-radius: 8px;
```

### Color Tokens Quick Reference

| Purpose | Token |
|---|---|
| Primary brand | `--color-brand-600` |
| Brand hover | `--color-brand-700` |
| Page background | `--color-surface-1` |
| Card / white surface | `--color-surface-0` |
| Nested section bg | `--color-surface-2` |
| Body text | `--color-gray-700` / `--color-gray-800` |
| Muted text | `--color-slate-500` |
| Border default | `--color-slate-200` |
| Border strong | `--color-slate-300` |
| Success | `--color-success` |
| Warning | `--color-warning` |
| Danger / Error | `--color-danger` |
| Info | `--color-info` |
| Focus ring shadow | `--color-focus-ring` |

---

## Class Naming Conventions

- **Layout shells**: `{shell}-shell`, e.g. `.dashboard-shell`, `.auth-shell`
- **Layout regions**: `{shell}-{region}`, e.g. `.dashboard-main`, `.tech-header`
- **Components**: `.{component}`, e.g. `.card`, `.btn`, `.badge`
- **Component variants**: `.{component}-{variant}`, e.g. `.btn-primary`, `.badge-success`
- **Component sizes**: `.{component}-{size}`, e.g. `.btn-sm`, `.btn-lg`
- **States**: `.active`, `.disabled`, `.is-invalid`, `.is-valid`, `.open`
- **Sidebar nav**: `.sidebar-nav-item`, `.sidebar-nav-icon`, `.sidebar-nav-group`
- **Page sections**: `{section}-section`, e.g. `.hero-section`, `.features-section`

---

## When to Use Which File

| Scenario | File |
|---|---|
| New reusable component (button, card, form, badge) | `components.css` |
| New layout shell or structural region | `layouts.css` |
| Page-specific section that is not reused | `pages.css` |
| Breakpoint override for any class | `responsive.css` |
| New color, spacing, radius, shadow value | `tokens.css` |
| Font faces, html/body, RTL default | `base.css` |

---

## How to Build a New Page

1. Choose the correct layout shell template:
   - Admin/staff pages → `{% extends "layouts/dashboard.html" %}`
   - Login/register → `{% extends "layouts/auth.html" %}`
   - Public landing → `{% extends "layouts/public.html" %}`
   - Technician mobile → `{% extends "layouts/technician.html" %}`
   - Error page → `{% extends "layouts/error.html" %}`
   - Invoice print → `{% extends "layouts/invoice_print.html" %}`

2. Use `{% block content %}` for main content.

3. Add a `page-header` at the top:
```html
{% include "components/page_header.html" with title="عنوان صفحه" subtitle="توضیح اختیاری" %}
```

4. Use `.card` for content panels:
```html
<div class="card">
  <div class="card-header">
    <h2 class="card-header-title">عنوان کارت</h2>
  </div>
  <div class="card-body">...</div>
</div>
```

5. Use `{% include "components/alert_message.html" %}` for Django messages.

---

## How to Build a New Form

```html
<form method="post">
  {% csrf_token %}
  {% include "components/form_errors.html" with form=form %}

  <div class="form-section">
    <h3 class="form-section-title">اطلاعات اصلی</h3>
    <div class="form-grid-2">
      <div class="form-group">
        <label class="form-label required">نام</label>
        <input type="text" name="name" class="form-control {% if form.name.errors %}is-invalid{% endif %}">
        {% if form.name.errors %}
          <span class="form-error">{{ form.name.errors.0 }}</span>
        {% endif %}
      </div>
    </div>
  </div>

  <div class="form-actions">
    <a href="..." class="btn btn-outline">انصراف</a>
    <button type="submit" class="btn btn-primary">ذخیره</button>
  </div>
</form>
```

**Rules:**
- Never rename form fields (Django form field names come from the backend).
- Never change `name=` attributes for visual reasons.
- Use `.form-grid-2` / `.form-grid-3` for responsive field layouts.
- Use `.form-label.required` to add the `*` indicator (CSS-only, no JS).

---

## How to Build a New Table

```html
<div class="card card-compact">
  {% include "components/table_toolbar.html" with search_value=request.GET.q %}
  <div class="table-wrapper">
    <table class="data-table">
      <thead>
        <tr>
          <th>شناسه</th>
          <th>نام</th>
          <th>وضعیت</th>
          <th>عملیات</th>
        </tr>
      </thead>
      <tbody>
        {% for obj in object_list %}
        <tr>
          <td>{{ obj.id }}</td>
          <td>{{ obj.name }}</td>
          <td>{% include "components/status_badge.html" with status=obj.status %}</td>
          <td>
            <a href="{{ obj.get_absolute_url }}" class="btn btn-ghost btn-sm btn-icon">...</a>
          </td>
        </tr>
        {% empty %}
        <tr><td colspan="4">{% include "components/empty_state.html" with title="موردی یافت نشد" %}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </div>
  {% include "components/pagination.html" with page_obj=page_obj %}
</div>
```

---

## How to Build a New Dashboard Card (Stat Card)

```html
<div class="stats-row">
  {% include "components/stat_card.html" with value=stats.total label="کل سفارش‌ها" icon="orders" color="blue" %}
  {% include "components/stat_card.html" with value=stats.done  label="تکمیل شده"   icon="check"  color="green" %}
  {% include "components/stat_card.html" with value=stats.money label="درآمد"        icon="money"  color="amber" %}
</div>
```

Available `color` values: `blue` (default), `green`, `amber`, `red`, `purple`, `indigo`
Available `icon` values: `orders`, `money`, `users`, `technician`, `invoice`, `company`, `check`, `clock`, `bell`

---

## How to Use Status Badges

The preferred method is the `status_badge.html` component which calls custom template
tags to resolve the Persian label and CSS classes automatically:

```html
{% include "components/status_badge.html" with status=order.status %}
```

For a manual badge without template tags:
```html
<span class="badge badge-success">تأیید شده</span>
<span class="badge badge-warning">در انتظار</span>
<span class="badge badge-danger">لغو شده</span>
<span class="badge badge-neutral">پیش‌نویس</span>
<span class="badge badge-info">ارسال شده</span>
```

---

## How to Keep RTL/LTR Correct

**RTL is the default** — `body { direction: rtl; }` is set in `base.css`.

For numbers, phone numbers, amounts, codes, and URLs use helper classes:

```html
<span class="num">۱۲۳۴۵</span>           <!-- tabular-nums, LTR -->
<span class="amount">۴۵۰,۰۰۰</span>       <!-- monetary amounts -->
<span class="phone-number">۰۹۱۲۱۲۳۴۵۶۷</span>
<span class="tracking-code">TRK-001</span>
<span class="ltr-inline">some-code-123</span>  <!-- inline LTR text -->
```

For LTR form fields (e.g. email, URL):
```html
<input type="email" class="form-control ltr-field">
```

---

## What NOT to Do

| Don't | Why |
|---|---|
| Random inline `style="color:#abc"` | Use tokens and component classes |
| Fake one-off colors | Every color must exist as a token |
| Page-specific button styles | Use `.btn .btn-primary` etc. |
| Direct hardcoded colors if a token exists | Tokens make global theme changes safe |
| Duplicated card / table / form patterns | Reuse components |
| Changing backend form `name=` for design | Breaks form submission |
| Adding `{% url %}` calls with invented view names | Will raise `NoReverseMatch` |
| Importing new CSS frameworks or CDN links | No external CDN; no npm |
| Using Alpine.js / HTMX if not already present | Not installed in this project |
| Putting `@media` queries inside components.css | Belongs in responsive.css only |
| Creating duplicate `@media` blocks | Merge into existing blocks in responsive.css |
