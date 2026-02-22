"""
Tests for the maintenance mode middleware.
"""

import json
import os
from unittest import mock

from django.test import TestCase
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from core.test_utils.utils import create_user, create_profile
from apps.core_app.middleware import MAINTENANCE_FLAG_FILE


class MaintenanceModeMiddlewareTests(TestCase):
    """Test maintenance mode middleware behavior."""

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        self.status_url = reverse("config_app:system-status")
        # Use an authenticated endpoint for testing blocked requests
        self.user = create_user(email="test@example.com", password="testpass123")
        self.profile = create_profile(user=self.user, username="testuser")
        # Ensure no maintenance flag exists before each test
        if MAINTENANCE_FLAG_FILE.exists():
            MAINTENANCE_FLAG_FILE.unlink()

    def tearDown(self):
        """Clean up after each test."""
        if MAINTENANCE_FLAG_FILE.exists():
            MAINTENANCE_FLAG_FILE.unlink()

    def _enable_maintenance(self, message="System maintenance", end_time=None, allow_admin=False):
        """Helper to enable maintenance mode via flag file."""
        MAINTENANCE_FLAG_FILE.write_text(json.dumps({
            'enabled': True,
            'message': message,
            'end_time': end_time,
            'allow_admin': allow_admin,
        }))

    def test_requests_allowed_when_maintenance_disabled(self):
        """Test that requests are allowed when maintenance mode is disabled."""
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        # Try to access an API endpoint
        res = self.client.get('/api/v1/auth/my-info/')

        # Should get through (may be 200 or 401 depending on auth, but not 503)
        self.assertNotEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_requests_blocked_when_maintenance_enabled(self):
        """Test that requests return 503 when maintenance mode is enabled."""
        self._enable_maintenance(message='System maintenance')

        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        # Try to access an API endpoint (not the status endpoint)
        res = self.client.get('/api/v1/profile/')

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = res.json()
        self.assertEqual(data['status'], 'maintenance')
        self.assertEqual(data['message'], 'System maintenance')

    def test_status_endpoint_accessible_during_maintenance(self):
        """Test that status endpoint is always accessible."""
        self._enable_maintenance(message='System maintenance')

        res = self.client.get(self.status_url)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'maintenance')

    def test_admin_endpoint_accessible_during_maintenance(self):
        """Test that admin endpoint is accessible during maintenance."""
        self._enable_maintenance()

        # Admin endpoint should not return 503
        res = self.client.get('/admin/')

        # Should get redirect or login page, not 503
        self.assertNotEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_static_files_accessible_during_maintenance(self):
        """Test that static file paths are not blocked."""
        self._enable_maintenance()

        res = self.client.get('/static/nonexistent.css')

        # Should get 404 not found, not 503
        self.assertNotEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_maintenance_response_includes_retry_after(self):
        """Test that maintenance response includes Retry-After header."""
        self._enable_maintenance(message='System maintenance')

        res = self.client.get('/api/v1/profile/')

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(res['Retry-After'], '300')

    def test_maintenance_response_is_json(self):
        """Test that maintenance response is JSON formatted."""
        self._enable_maintenance(message='System maintenance')

        res = self.client.get('/api/v1/profile/')

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(res['Content-Type'], 'application/json')

    def test_maintenance_response_includes_estimated_end_time(self):
        """Test that maintenance response includes estimated end time if set."""
        self._enable_maintenance(
            message='System maintenance',
            end_time='2024-01-15T14:00:00'
        )

        res = self.client.get('/api/v1/profile/')

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = res.json()
        self.assertEqual(data['estimated_end_time'], '2024-01-15T14:00:00')

    def test_admin_users_allowed_when_allow_admin_enabled(self):
        """Test that admin users can access site when allow_admin is set."""
        # Create an admin user
        admin_user = create_user(
            email="admin@example.com",
            password="adminpass123",
            is_staff=True,
        )
        admin_profile = create_profile(user=admin_user, username="adminuser")

        self._enable_maintenance(allow_admin=True)

        # Use login() for session auth so middleware sees the user
        self.client.login(email="admin@example.com", password="adminpass123")
        self.client.force_authenticate(user=admin_user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(admin_profile.public_id))

        res = self.client.get('/api/v1/auth/my-info/')

        # Admin should get through (not 503)
        self.assertNotEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_regular_users_blocked_even_with_allow_admin(self):
        """Test that regular users are still blocked when allow_admin is set."""
        self._enable_maintenance(allow_admin=True)

        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.public_id))

        res = self.client.get('/api/v1/profile/')

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_unauthenticated_requests_blocked_during_maintenance(self):
        """Test that unauthenticated requests are blocked during maintenance."""
        self._enable_maintenance(message='System maintenance')

        res = self.client.get('/api/v1/profile/')

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_wellknown_paths_accessible_during_maintenance(self):
        """Test that /.well-known/ paths are accessible for SSL renewal."""
        self._enable_maintenance()

        res = self.client.get('/.well-known/acme-challenge/test')

        # Should get 404 not found, not 503
        self.assertNotEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)

    def test_env_var_fallback_works(self):
        """Test that environment variable fallback works when no flag file."""
        with mock.patch.dict(os.environ, {
            'MAINTENANCE_MODE': '1',
            'MAINTENANCE_MESSAGE': 'Env maintenance',
        }):
            res = self.client.get('/api/v1/profile/')

        self.assertEqual(res.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        data = res.json()
        self.assertEqual(data['message'], 'Env maintenance')
