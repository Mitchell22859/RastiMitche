# Rasti Service - Architecture Documentation

## Overview

Rasti Service is a production-grade **multi-tenant SaaS platform** for service companies.
Each company (tenant) gets an isolated workspace with its own users, orders, invoices,
payment gateways, and public page — all running on a single database and codebase.

---

## Multi-Tenancy Strategy

### Path-Based Tenancy (NOT Schema-Based)

Tenant resolution happens from the **URL path**, not from database schemas or subdomains.

```
/n54/           → Company with code "n54"
/n54/orders/    → Orders for company "n54"
/n54/admin/     → Dashboard for company "n54"
```

### How It Works

1. **TenantMiddleware** intercepts every request
2. Extracts the first path segment as `company_code`
3. Looks up `Company` by code
4. If not found or inactive → **404**
5. Attaches `request.company` for all downstream code
6. Platform-level routes (`/loginlogin/`, `/admin/`, `/static/`) bypass resolution

### The Golden Rule

```python
# ✅ CORRECT — always filter by company
Order.objects.filter(company=request.company)

# ❌ WRONG — NEVER do this for tenant models
Order.objects.all()
```

Every tenant-scoped model inherits `CompanyOwnedModel` which has a `company` FK.

---

## Architecture Pattern: Service Layer

We follow **Clean Architecture** principles with a Service Layer pattern:

```
┌─────────────────────────────────────────┐
│             Views (thin)                 │
│   - HTTP request/response only          │
│   - Delegates to services/selectors     │
└────────────┬───────────────┬────────────┘
             │               │
     ┌───────▼───────┐ ┌────▼────────────┐
     │   Services    │ │   Selectors     │
     │ (write ops)   │ │ (read ops)      │
     │ - business    │ │ - query building│
     │   logic       │ │ - filtering     │
     └───────┬───────┘ └────┬────────────┘
             │               │
     ┌───────▼───────────────▼────────────┐
     │            Models                   │
     │   - Data structure only            │
     │   - No business logic              │
     └────────────────────────────────────┘
```

### Pattern Files

| File             | Purpose                          |
|------------------|----------------------------------|
| `models.py`      | Data models, no business logic   |
| `services.py`    | Write operations, business logic |
| `selectors.py`   | Read queries, always return QS   |
| `permissions.py` | Access control helpers           |
| `views.py`       | Thin HTTP layer                  |
| `urls.py`        | URL routing                      |
| `admin.py`       | Django admin configuration       |

---

## Role System

| Role             | Scope    | Access                                    |
|------------------|----------|-------------------------------------------|
| PLATFORM_OWNER   | Platform | Full platform admin (`/loginlogin/`)      |
| COMPANY_ADMIN    | Tenant   | Full company dashboard                    |
| COMPANY_STAFF    | Tenant   | Limited company operations                |
| TECHNICIAN       | Tenant   | Field work, assigned orders only          |
| CUSTOMER         | Tenant   | View own orders and invoices              |

---

## Project Structure

```
saaSwebsite/
├── config/
│   ├── settings/
│   │   ├── base.py          # Shared settings
│   │   ├── local.py         # Dev overrides
│   │   └── production.py    # Production security
│   ├── urls.py              # Root URL config
│   ├── wsgi.py
│   └── asgi.py
├── apps/
│   ├── common/              # Shared base classes
│   │   ├── models.py        # CompanyOwnedModel, TimeStampedModel
│   │   ├── services.py      # BaseService pattern
│   │   ├── selectors.py     # BaseSelector, BaseCompanySelector
│   │   └── permissions.py   # Decorators: require_tenant, require_role
│   ├── platform_core/       # Platform owner features
│   ├── tenants/             # Multi-tenancy core
│   │   ├── models.py        # Company, CompanyPage
│   │   └── middleware.py    # TenantMiddleware ⭐
│   ├── accounts/            # Users, Technicians, Customers
│   ├── orders/              # Service orders
│   ├── invoices/            # Invoice generation
│   ├── payments/            # Payment gateways & transactions
│   ├── billing/             # Platform-to-company billing
│   ├── notifications/       # In-app notifications
│   ├── sms/                 # SMS provider integration
│   ├── reports/             # Report generation
│   └── dashboard/           # Company admin dashboard
├── templates/               # Django templates (future)
├── static/                  # Static assets (future)
└── manage.py
```

---

## Security Boundaries

### Data Isolation
- Every tenant model has `company` FK with db_index
- Selectors enforce company filtering at query level
- Middleware prevents access to inactive companies
- Cross-tenant access is blocked by `require_company_membership` decorator

### Permission Decorators
```python
@require_tenant              # Ensures request.company exists
@require_company_membership  # User belongs to this company
@require_role("COMPANY_ADMIN")  # User has required role
```

---

## URL Architecture

```
# Platform Level (bypasses tenant middleware)
/loginlogin/          → PlatformCore dashboard
/admin/               → Django admin

# Tenant Level (middleware resolves company)
/<code>/              → Company public page
/<code>/login/        → Tenant authentication
/<code>/admin/        → Company dashboard
/<code>/orders/       → Order management
/<code>/invoices/     → Invoice management
/<code>/payments/     → Payment management
/<code>/reports/      → Reports
/<code>/notifications/ → Notifications
```

---

## Development Phases

### Phase 1 (Current): Foundation ✅
- Project structure
- Multi-tenancy middleware
- Base models and patterns
- Role system
- URL routing

### Phase 2: Authentication & Authorization
- Login/logout flow (phone + OTP)
- Session management
- Permission enforcement
- Password reset

### Phase 3: Core Business Logic
- Order CRUD with status workflow
- Invoice generation from orders
- Customer management
- Technician assignment logic

### Phase 4: Payments & Billing
- Payment gateway integration (ZarinPal, IDPay)
- Payment verification callbacks
- Platform subscription billing

### Phase 5: Communication
- SMS integration (Kavenegar)
- In-app notifications
- Email notifications

### Phase 6: Dashboard & Reports
- Dashboard widgets with stats
- Report generation
- Export functionality (PDF, Excel)

### Phase 7: Public Pages
- Company landing pages
- SEO optimization
- Customer self-service portal

### Phase 8: API Layer
- Django REST Framework integration
- API authentication (JWT)
- Mobile API endpoints

### Phase 9: Production Hardening
- Caching (Redis)
- Background tasks (Celery)
- Monitoring & logging
- Load testing
- Backup strategy
