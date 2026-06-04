# Fast local development workflow

This clean project intentionally excludes local-only and phase-only files:

- `.git/`
- `.venv/`
- `db.sqlite3`
- `.env`
- `__pycache__/`
- `tests_phase*.py`
- old phase patch README files

## First setup

```powershell
cd C:\Projects\saaSwebsite\saaSwebsite
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
```

## Daily startup

```powershell
cd C:\Projects\saaSwebsite\saaSwebsite
.\.venv\Scripts\Activate.ps1
python manage.py runserver
```

## After a small template/view change

```powershell
python manage.py check
```

## After changing order logic

```powershell
python manage.py check
python manage.py test apps.orders
```

## Before closing a full phase

```powershell
python manage.py test apps.orders apps.tenants apps.accounts
```

## Before release/deployment

```powershell
python manage.py test
```

Do not run the full project test suite after every small change. Use targeted tests while developing, and run the full suite only at phase boundaries.
