"""
Platform Core - Health Check Endpoints.

/health/ — basic application health
/health/db/ — database connectivity check

These are used by load balancers, monitoring, and deployment checks.
Exempt from tenant resolution (in TENANT_EXEMPT_PREFIXES).
"""
from django.db import connection
from django.http import JsonResponse


def health_check(request):
    """Basic app health check. Returns 200 if the app is running."""
    return JsonResponse({
        "status": "healthy",
        "service": "rasti-service",
    })


def health_db_check(request):
    """
    Database connectivity health check.
    Returns 200 if DB connection succeeds, 503 otherwise.
    """
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
        return JsonResponse({
            "status": "healthy",
            "database": "connected",
        })
    except Exception as e:
        return JsonResponse(
            {"status": "unhealthy", "database": "disconnected", "error": str(e)},
            status=503,
        )
