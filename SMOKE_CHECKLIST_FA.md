# Smoke Checklist - RastiService

Use this after any cleanup or feature change.

## Commands

```powershell
cd D:\mySaaSsite\current_project
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py migrate --plan
```

## Browser checks

```text
http://127.0.0.1:8000/loginlogin/
http://127.0.0.1:8000/favicon.ico
http://127.0.0.1:8000/n54/
http://127.0.0.1:8000/n54/login/
http://127.0.0.1:8000/n54/admin/
http://127.0.0.1:8000/n54/admin/orders/
http://127.0.0.1:8000/n54/admin/sms/templates/
http://127.0.0.1:8000/n54/tech/
http://127.0.0.1:8000/n54/tech/orders/available/
http://127.0.0.1:8000/n54/tech/orders/my/
```

## Expected result

- Django check has no issues.
- makemigrations dry-run says "No changes detected".
- migrate plan does not show unexpected dangerous operations.
- The login page returns 200.
- The favicon URL should not be handled as a tenant code.
- Technician order links should use /tech/orders/...
