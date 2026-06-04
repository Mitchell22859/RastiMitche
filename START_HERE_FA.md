# START HERE - RastiService

This file is the local baseline guide after Phase 28.

## Project location

Main project:

```text
D:\mySaaSsite\current_project
```

Archive/reference code:

```text
D:\mySaaSsite\reference_old
```

Documentation:

```text
D:\mySaaSsite\docs
```

## Important URL structure

Platform owner panel:

```text
/loginlogin/
```

Company public/customer paths:

```text
/<companyCode>/
```

Company admin/operator panel:

```text
/<companyCode>/admin/
```

Technician panel:

```text
/<companyCode>/tech/
```

## Demo company

Default seeded company code:

```text
n54
```

Useful local URLs:

```text
http://127.0.0.1:8000/loginlogin/
http://127.0.0.1:8000/n54/
http://127.0.0.1:8000/n54/login/
http://127.0.0.1:8000/n54/admin/
http://127.0.0.1:8000/n54/tech/
http://127.0.0.1:8000/n54/tech/orders/available/
http://127.0.0.1:8000/n54/tech/orders/my/
```

## Demo users

```text
platform_owner / password123
n54_admin      / password123
n54_tech       / password123
n54_customer   / password123
```

## Run project

```powershell
cd D:\mySaaSsite\current_project
python manage.py runserver
```

## Reset local database

Only do this when local data is not important.

```powershell
cd D:\mySaaSsite\current_project
Remove-Item .\db.sqlite3 -Force -ErrorAction SilentlyContinue
python manage.py migrate
python manage.py seed_demo
python manage.py seed_sms_templates --company-code n54
python manage.py seed_rasti_order_data --company-code n54
python manage.py check
```

## Do not run

Tests were intentionally removed from this project.

```powershell
python manage.py test
```

## Daily smoke check

```powershell
PowerShell -ExecutionPolicy Bypass -File "D:\mySaaSsite\current_project\scripts\dev_smoke_check.ps1"
```
