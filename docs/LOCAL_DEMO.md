# Rasti Service - Local Demo Guide

## Quick Start (5 minutes)

```bash
# 1. Clone
git clone https://github.com/manouchehr94-ux/saaSwebsite.git
cd saaSwebsite

# 2. Install
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 3. Setup database (SQLite for quick demo)
export DJANGO_SETTINGS_MODULE=config.settings.local
python manage.py migrate

# 4. Seed demo data
python manage.py seed_demo

# 5. Run server
python manage.py runserver
```

## Test Credentials

| Role | Username | Password | Login URL |
|------|----------|----------|-----------|
| Platform Owner | `platform_owner` | `password123` | http://localhost:8000/loginlogin/ |
| Company Admin | `n54_admin` | `password123` | http://localhost:8000/n54/login/ |
| Technician | `n54_tech` | `password123` | http://localhost:8000/n54/login/ |
| Customer | `n54_customer` | `password123` | http://localhost:8000/n54/login/ |

## Key URLs

### Platform
- Platform Login: http://localhost:8000/loginlogin/
- Platform Dashboard: http://localhost:8000/loginlogin/dashboard/
- Platform Reports: http://localhost:8000/loginlogin/reports/

### Company (N54)
- Public Page: http://localhost:8000/n54/
- Service Request: http://localhost:8000/n54/request/
- Login: http://localhost:8000/n54/login/
- Dashboard: http://localhost:8000/n54/admin/
- Orders: http://localhost:8000/n54/orders/
- Invoices: http://localhost:8000/n54/invoices/
- Reports: http://localhost:8000/n54/reports/
- Notifications: http://localhost:8000/n54/notifications/
- SMS Outbox: http://localhost:8000/n54/admin/sms/

### REST API
- Orders API: http://localhost:8000/api/n54/orders/
- Services API: http://localhost:8000/api/n54/services/
- Invoices API: http://localhost:8000/api/n54/invoices/
- Platform Companies: http://localhost:8000/api/platform/companies/

### Health
- App Health: http://localhost:8000/health/
- DB Health: http://localhost:8000/health/db/

## Demo Data Included

| Data | Details |
|------|---------|
| Company | N54 Service (code: n54) |
| Services | Plumbing, Electrical, HVAC, Painting |
| Orders | 1 NEW, 1 IN_PROGRESS, 1 DONE |
| Invoices | 1 ISSUED, 1 PAID |
| Payment Gateway | Fake provider (for testing) |
| SMS Provider | Fake provider + sample outbox |
| Notifications | 4 sample notifications |
| Technician Skills | plumbing, electrical, hvac |

## Exploring the Demo

### As Platform Owner
1. Login at /loginlogin/ with `platform_owner` / `password123`
2. View dashboard with company stats
3. View reports at /loginlogin/reports/
4. Access API at /api/platform/companies/

### As Company Admin
1. Login at /n54/login/ with `n54_admin` / `password123`
2. View dashboard with order stats and revenue
3. Manage orders, invoices, reports
4. Edit public page at /n54/admin/page/
5. View service requests at /n54/admin/requests/

### As Technician
1. Login at /n54/login/ with `n54_tech` / `password123`
2. View available orders to accept
3. View assigned orders

### As Customer
1. Login at /n54/login/ with `n54_customer` / `password123`
2. View my orders and invoices
3. Pay invoices (uses fake gateway)

### Public Visitor (no login needed)
1. Visit /n54/ to see company public page
2. Visit /n54/request/ to submit a service request
3. Access /api/n54/services/ for service listing

## Running Tests

```bash
DJANGO_SETTINGS_MODULE=config.settings.test python manage.py test
```

## Resetting Demo Data

```bash
# Delete database and re-create
python manage.py flush --noinput
python manage.py seed_demo
```
