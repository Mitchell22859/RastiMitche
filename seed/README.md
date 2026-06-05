# Seed Scripts

This folder contains the minimal local development seed for Rasti Service.

---

## `minimal_seed_n54.py`

Creates the bare minimum records needed to start local development.

### What it creates

| Record | Details |
|---|---|
| Company | code=`n54`, name=`شرکت نمونه N54`, `is_active=True` |
| Platform owner | username=`platform_owner`, superuser, no company |
| Company admin | username=`n54_admin`, role=`COMPANY_ADMIN`, company=`n54` |
| Technician | username=`n54_tech`, role=`TECHNICIAN`, company=`n54` + Technician profile |

### What it does NOT create

- No demo orders
- No demo invoices
- No demo customers
- No demo SMS outbox records
- No demo payments or transactions
- No demo notifications

### How to run

```bash
# From the project root:
python seed/minimal_seed_n54.py
```

### Default credentials

| Username | Role | Password |
|---|---|---|
| `platform_owner` | PLATFORM_OWNER | `Admin@1234` |
| `n54_admin` | COMPANY_ADMIN | `Admin@1234` |
| `n54_tech` | TECHNICIAN | `Admin@1234` |

> **WARNING:** These are default development credentials.  
> Never use them in a production or staging environment.  
> Change all passwords immediately after first login.

### Idempotent

Safe to run multiple times. Uses `get_or_create` — will not duplicate
users or companies if they already exist.

---

## SMS Master Templates

SMS master templates are bootstrapped automatically after every `migrate`
run via a `post_migrate` signal in `apps/sms/apps.py`.

You can also run it manually:

```bash
python manage.py ensure_sms_master_templates
```

To provision SMS templates for all active companies:

```bash
python manage.py seed_sms_templates
```

---

## Full setup sequence for a fresh local environment

```bash
python manage.py migrate          # also bootstraps SMS master templates
python seed/minimal_seed_n54.py   # creates users and company
python manage.py runserver
```
