"""
Production settings for Rasti Service.

All security features enabled. Requires proper environment variables.

IMPORTANT:
- Never deploy with DEBUG=True.
- SECRET_KEY must be set in the environment (no insecure fallback).
- ALLOWED_HOSTS must be set explicitly.
- CSRF_TRUSTED_ORIGINS must include your HTTPS domain(s).
- KYC media files must NOT be served directly by the web server.

Run deployment check:
    DJANGO_SETTINGS_MODULE=config.settings.production python manage.py check --deploy
"""
from decouple import Csv, config

from .base import *  # noqa: F401, F403

# =============================================================================
# CORE SECURITY
# =============================================================================

DEBUG = False

# SECRET_KEY: In production, must come from environment. No insecure fallback.
SECRET_KEY = config("DJANGO_SECRET_KEY")

# ALLOWED_HOSTS: Must be explicitly set in production.
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="", cast=Csv())

# CSRF: Trusted origins must include HTTPS domains.
CSRF_TRUSTED_ORIGINS = config(
    "DJANGO_CSRF_TRUSTED_ORIGINS",
    default="",
    cast=Csv(),
)

# =============================================================================
# HTTPS / SSL
# =============================================================================

SECURE_SSL_REDIRECT = config("DJANGO_SECURE_SSL_REDIRECT", default=True, cast=bool)
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# =============================================================================
# HSTS (HTTP Strict Transport Security)
# =============================================================================

SECURE_HSTS_SECONDS = config("DJANGO_SECURE_HSTS_SECONDS", default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = config("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True, cast=bool)
SECURE_HSTS_PRELOAD = config("DJANGO_SECURE_HSTS_PRELOAD", default=True, cast=bool)

# =============================================================================
# CONTENT SECURITY
# =============================================================================

SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# =============================================================================
# SESSION SECURITY
# =============================================================================

SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_ENGINE = "django.contrib.sessions.backends.db"

# =============================================================================
# CSRF COOKIE SECURITY
# =============================================================================

CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True

# =============================================================================
# PAYMENT GATEWAY
# =============================================================================

PAYMENT_EXPIRATION_MINUTES = config("PAYMENT_EXPIRATION_MINUTES", default=30, cast=int)

# =============================================================================
# LOGGING (production)
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {module} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
