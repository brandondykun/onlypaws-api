"""
Tests for the system status API endpoint.
"""

import json
import os
from pathlib import Path
from unittest import mock

from django.test import TestCase

from rest_framework.test import APIClient
from rest_framework import status

from .util import SYSTEM_STATUS_URL
from apps.core_app.middleware import MAINTENANCE_FLAG_FILE


class SystemStatusApiTests(TestCase):
    """Test system status API endpoint."""

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()
        # Ensure no maintenance flag exists before each test
        if MAINTENANCE_FLAG_FILE.exists():
            MAINTENANCE_FLAG_FILE.unlink()

    def tearDown(self):
        """Clean up after each test."""
        # Remove maintenance flag if it exists
        if MAINTENANCE_FLAG_FILE.exists():
            MAINTENANCE_FLAG_FILE.unlink()

    def test_status_endpoint_public_access(self):
        """Test that status endpoint is publicly accessible without authentication."""
        res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_status_returns_operational_by_default(self):
        """Test that status returns 'operational' when maintenance mode is not set."""
        res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'operational')
        self.assertIsNone(res.data['message'])

    def test_status_returns_maintenance_when_flag_file_exists(self):
        """Test that status returns 'maintenance' when flag file exists."""
        # Create maintenance flag file
        MAINTENANCE_FLAG_FILE.write_text(json.dumps({
            'enabled': True,
            'message': 'System upgrade in progress',
            'end_time': None,
            'allow_admin': False,
        }))

        res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'maintenance')
        self.assertEqual(res.data['message'], 'System upgrade in progress')

    def test_status_includes_estimated_end_time(self):
        """Test that status includes estimated end time when provided."""
        MAINTENANCE_FLAG_FILE.write_text(json.dumps({
            'enabled': True,
            'message': 'Scheduled maintenance',
            'end_time': '2024-01-15T14:00:00',
            'allow_admin': False,
        }))

        res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'maintenance')
        self.assertIsNotNone(res.data['estimated_end_time'])

    def test_status_handles_invalid_end_time(self):
        """Test that status handles invalid end time gracefully."""
        MAINTENANCE_FLAG_FILE.write_text(json.dumps({
            'enabled': True,
            'message': 'Maintenance',
            'end_time': 'invalid-date',
            'allow_admin': False,
        }))

        res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'maintenance')
        self.assertIsNone(res.data['estimated_end_time'])

    def test_status_message_null_when_operational(self):
        """Test that message is null when system is operational."""
        res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['status'], 'operational')
        self.assertIsNone(res.data['message'])

    def test_status_response_format(self):
        """Test that response has correct format."""
        res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertIn('status', res.data)
        self.assertIn('message', res.data)
        self.assertIn('estimated_end_time', res.data)

    def test_status_env_var_fallback(self):
        """Test that MAINTENANCE_MODE env var works as fallback."""
        with mock.patch.dict(os.environ, {
            'MAINTENANCE_MODE': '1',
            'MAINTENANCE_MESSAGE': 'Env var maintenance',
        }):
            res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.data['status'], 'maintenance')
        self.assertEqual(res.data['message'], 'Env var maintenance')

    def test_flag_file_takes_precedence_over_env_var(self):
        """Test that flag file takes precedence over environment variable."""
        # Create flag file
        MAINTENANCE_FLAG_FILE.write_text(json.dumps({
            'enabled': True,
            'message': 'File-based maintenance',
            'end_time': None,
            'allow_admin': False,
        }))

        # Also set env var (should be ignored)
        with mock.patch.dict(os.environ, {
            'MAINTENANCE_MODE': '1',
            'MAINTENANCE_MESSAGE': 'Env var maintenance',
        }):
            res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.data['status'], 'maintenance')
        self.assertEqual(res.data['message'], 'File-based maintenance')

    def test_status_operational_when_no_flag_and_no_env(self):
        """Test that system is operational when no flag file and no env var."""
        res = self.client.get(SYSTEM_STATUS_URL)

        self.assertEqual(res.data['status'], 'operational')
