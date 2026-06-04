# Rasti Service - Deployment Guide

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DJANGO_SECRET_KEY` | **Yes** (production) | `insecure-change-me` | Django secret key |
| `DEBUG` | No | `False` | Enable debug mode |
| `ALLOWED_HOSTS` | **Yes** (production) | `*` | Comma-separated allowed hosts |
| `DB_NAME` | Yes | `rasti_service` | PostgreSQL database name |
| `DB_USER` | Yes | `postgres` | Database user |
| `DB_PASSWORD` | Yes | `` | Database password |
| `DB_HOST` | Yes | `localhost` | Database host |
| `DB_PORT` | No | `5432` | Database port |
| `DATABASE_URL` | No | `` | Full database URL (overrides individual DB_* vars) |
| `CSRF_TRUSTED_ORIGINS` | Yes (production) | `http://localhost:8000` | Comma-separated trusted origins |
| `SECURE_SSL_REDIRECT` | No | `True` | Redirect HTTP to HTTPS |

## Local Setup

```bash
# 1. Clone and enter project
git clone https://github.com/manouchehr94-ux/saaSwebsite.git
cd saaSwebsite

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Create .env file
cat > .env << EOF
DEBUG=True
DJANGO_SECRET_KEY=your-dev-secret-key
DB_NAME=rasti_service
DB_USER=postgres
DB_PASSWORD=your-password
DB_HOST=localhost
DB_PORT=5432
EOF

# 5. Create database
createdb rasti_service

# 6. Run migrations
python manage.py migrate

# 7. Create superuser (platform owner)
python manage.py createsuperuser

# 8. Collect static files
python manage.py collectstatic --noinput

# 9. Run development server
python manage.py runserver
```

## Production Setup

```bash
# 1. Set environment variables (e.g., via systemd, Docker, or .env)
export DJANGO_SETTINGS_MODULE=config.settings.production
export DJANGO_SECRET_KEY="your-production-secret-key"
export ALLOWED_HOSTS="yourdomain.com,www.yourdomain.com"
export DB_NAME=rasti_service
export DB_USER=rasti_user
export DB_PASSWORD="strong-password"
export DB_HOST=db.internal
export CSRF_TRUSTED_ORIGINS="https://yourdomain.com"

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run migrations
python manage.py migrate

# 4. Collect static files
python manage.py collectstatic --noinput

# 5. Run with gunicorn
gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 4
```

## Migration Commands

```bash
# Generate migrations (after model changes)
python manage.py makemigrations

# Apply migrations
python manage.py migrate

# Show migration status
python manage.py showmigrations
```

## Static Files

```bash
# Collect all static files to STATIC_ROOT
python manage.py collectstatic --noinput

# WhiteNoise serves static files in production
# No need for separate nginx static config
```

## Creating Superuser (Platform Owner)

```bash
python manage.py createsuperuser
# Enter phone number (used as username)
# This creates a PLATFORM_OWNER user who can access /loginlogin/
```

## Health Checks

- `/health/` — Returns `{"status": "healthy"}` if app is running
- `/health/db/` — Returns `{"status": "healthy", "database": "connected"}` if DB is reachable

Use these for load balancer health checks and monitoring.

## Deployment Checklist

- [ ] `DEBUG=False` in production
- [ ] `DJANGO_SECRET_KEY` is a strong random value
- [ ] `ALLOWED_HOSTS` is set to your domain(s)
- [ ] `CSRF_TRUSTED_ORIGINS` includes your domain with protocol
- [ ] Database credentials are secure
- [ ] `python manage.py check --deploy` passes
- [ ] `python manage.py migrate` has been run
- [ ] `python manage.py collectstatic` has been run
- [ ] Platform owner (superuser) has been created
- [ ] Health endpoints are accessible: `/health/` and `/health/db/`
- [ ] HTTPS is configured (SSL certificate)
- [ ] Reverse proxy forwards `X-Forwarded-Proto` header
- [ ] Backups are configured for the database
- [ ] Monitoring is set up (health checks, error tracking)

## Docker (Optional)

```dockerfile
FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN python manage.py collectstatic --noinput

EXPOSE 8000
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "4"]
```

## Architecture Notes

- **Path-based multi-tenancy**: Tenant resolved from URL path (not schema/subdomain)
- **Middleware**: `TenantMiddleware` attaches `request.company` to all tenant requests
- **Static files**: Served by WhiteNoise (no separate nginx needed for static)
- **Session auth**: Currently using Django sessions (JWT can be added later)
- **Background jobs**: Architecture is Celery-ready (services are synchronous for now)
