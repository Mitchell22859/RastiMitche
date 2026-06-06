"""
P10-PRODUCTION-SECURITY-SETTINGS: Verify production settings are secure.

Tests that production settings module enforces security requirements when
imported with appropriate environment variables.
"""
import os
from unittest.mock import patch

from django.test import TestCase, SimpleTestCase, override_settings


class ProductionSettingsSecurityTest(SimpleTestCase):
    """
    Verify that config.settings.production enforces security standards.

    These tests import the production settings module with fake environment
    variables to verify security flags are set correctly.
    """

    def _load_production_settings(self):
        """Import production settings with minimal fake env vars."""
        env = {
            "DJANGO_SECRET_KEY": "test-secret-key-for-unit-test-only-not-real",
            "DJANGO_ALLOWED_HOSTS": "testserver.example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://testserver.example.com",
            "DB_NAME": "test_db",
            "DB_USER": "test_user",
            "DB_PASSWORD": "test_pass",
            "DB_HOST": "localhost",
            "DB_PORT": "5432",
            "DATABASE_URL": "",
            "DJANGO_SECURE_SSL_REDIRECT": "False",  # Disable for test
        }
        with patch.dict(os.environ, env, clear=False):
            import importlib
            import config.settings.production as prod_settings
            importlib.reload(prod_settings)
            return prod_settings

    def test_debug_is_false(self):
        """Production settings must have DEBUG=False."""
        settings = self._load_production_settings()
        self.assertFalse(settings.DEBUG)

    def test_session_cookie_secure(self):
        """Production settings must have SESSION_COOKIE_SECURE=True."""
        settings = self._load_production_settings()
        self.assertTrue(settings.SESSION_COOKIE_SECURE)

    def test_csrf_cookie_secure(self):
        """Production settings must have CSRF_COOKIE_SECURE=True."""
        settings = self._load_production_settings()
        self.assertTrue(settings.CSRF_COOKIE_SECURE)

    def test_secure_content_type_nosniff(self):
        """Production settings must have SECURE_CONTENT_TYPE_NOSNIFF=True."""
        settings = self._load_production_settings()
        self.assertTrue(settings.SECURE_CONTENT_TYPE_NOSNIFF)

    def test_x_frame_options_deny(self):
        """Production settings must have X_FRAME_OPTIONS=DENY."""
        settings = self._load_production_settings()
        self.assertEqual(settings.X_FRAME_OPTIONS, "DENY")

    def test_session_cookie_httponly(self):
        """Production settings must have SESSION_COOKIE_HTTPONLY=True."""
        settings = self._load_production_settings()
        self.assertTrue(settings.SESSION_COOKIE_HTTPONLY)

    def test_hsts_seconds_set(self):
        """Production settings must have SECURE_HSTS_SECONDS > 0."""
        settings = self._load_production_settings()
        self.assertGreater(settings.SECURE_HSTS_SECONDS, 0)

    def test_secret_key_no_insecure_default(self):
        """Production settings must NOT use the insecure default SECRET_KEY."""
        settings = self._load_production_settings()
        # The insecure default from base.py
        self.assertNotEqual(settings.SECRET_KEY, "insecure-change-me-in-production")

    def test_allowed_hosts_from_environment(self):
        """Production ALLOWED_HOSTS must be set from environment."""
        settings = self._load_production_settings()
        self.assertIn("testserver.example.com", settings.ALLOWED_HOSTS)
        # Must not be wildcard
        self.assertNotIn("*", settings.ALLOWED_HOSTS)

    def test_secure_referrer_policy_set(self):
        """Production settings must have SECURE_REFERRER_POLICY set."""
        settings = self._load_production_settings()
        self.assertTrue(hasattr(settings, "SECURE_REFERRER_POLICY"))
        self.assertTrue(settings.SECURE_REFERRER_POLICY)

    def test_secure_proxy_ssl_header_set(self):
        """Production settings must configure SECURE_PROXY_SSL_HEADER for reverse proxy."""
        settings = self._load_production_settings()
        self.assertEqual(
            settings.SECURE_PROXY_SSL_HEADER,
            ("HTTP_X_FORWARDED_PROTO", "https"),
        )


class MediaServingSecurityTest(SimpleTestCase):
    """Verify that media files are only served by Django in DEBUG mode."""

    def test_media_not_served_when_debug_false(self):
        """config/urls.py should not add media URL patterns when DEBUG=False."""
        from django.conf import settings

        # In test environment (local.py), DEBUG is True.
        # We verify the code structure: the URL serving is guarded by `if settings.DEBUG`.
        # This is a documentation/structural check.
        import config.urls
        source_file = config.urls.__file__

        with open(source_file, "r", encoding="utf-8") as f:
            content = f.read()

        # Verify the media serving is conditional on DEBUG
        self.assertIn("if settings.DEBUG:", content)
        self.assertIn("static(settings.MEDIA_URL", content)

    def test_debug_media_guard_exists_in_urls(self):
        """The media serving block must be inside an if DEBUG guard."""
        import config.urls
        source_file = config.urls.__file__

        with open(source_file, "r", encoding="utf-8") as f:
            lines = f.readlines()

        # Find the media serving line and verify it's after the DEBUG check
        found_debug_check = False
        found_media_static = False
        for line in lines:
            if "if settings.DEBUG:" in line:
                found_debug_check = True
            if found_debug_check and "static(settings.MEDIA_URL" in line:
                found_media_static = True
                break

        self.assertTrue(
            found_debug_check and found_media_static,
            "Media serving must be inside `if settings.DEBUG:` block"
        )
