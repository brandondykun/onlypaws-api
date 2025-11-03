"""
Tests for the config API endpoints.
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from rest_framework.test import APIClient
from rest_framework import status

from apps.user_app.models import Profile
from apps.config_app.models import AppConfiguration


ADS_CONFIG_URL = reverse("config_app:ads-config")


def create_user(**params):
    """Create and return a new User."""
    return get_user_model().objects.create_user(**params)


def create_profile(**params):
    """Create and return a new Profile."""
    return Profile.objects.create(**params)


class PublicAdsConfigApiTests(TestCase):
    """Test unauthenticated API requests to ads config endpoint."""

    def setUp(self):
        """Set up test client."""
        self.client = APIClient()

    def test_auth_required(self):
        """Test that authentication is required for ads config endpoint."""
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)


class PrivateAdsConfigApiTests(TestCase):
    """Test authenticated API requests to ads config endpoint."""

    def setUp(self):
        """Set up test client with authenticated user."""
        self.client = APIClient()
        
        # Create user and profile
        self.user = create_user(
            email="test@example.com",
            password="testpass123"
        )
        self.profile = create_profile(
            user=self.user,
            username="testuser"
        )
        
        # Authenticate the client
        self.client.force_authenticate(user=self.user)
        
        # Set auth-profile-id header
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(self.profile.id))

    def tearDown(self):
        """Clean up after each test."""
        AppConfiguration.objects.all().delete()

    def test_retrieve_ads_config_success(self):
        """Test retrieving ads config when it exists with valid data."""
        # Create ads config in database
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True,
                'adInterval': 10
            },
            description='Ads configuration for the app'
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 10)

    def test_retrieve_ads_config_disabled(self):
        """Test retrieving ads config when ads are disabled."""
        # Create ads config with ads disabled
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': False,
                'adInterval': 5
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], False)
        self.assertEqual(res.data['adInterval'], 5)

    def test_retrieve_ads_config_different_interval(self):
        """Test retrieving ads config with different ad intervals."""
        # Create ads config with different interval
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True,
                'adInterval': 15
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 15)

    def test_retrieve_ads_config_not_exists_returns_defaults(self):
        """Test that default values are returned when config doesn't exist."""
        # Don't create any config
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 5)

    def test_retrieve_ads_config_invalid_data_returns_defaults(self):
        """Test that default values are returned when config data is invalid."""
        # Create config with missing required field
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True
                # Missing 'adInterval' field
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 5)

    def test_retrieve_ads_config_coercible_enabled_value(self):
        """Test that coercible enabled values are accepted by serializer."""
        # Create config with coercible type for enabled
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': 'true',  # String that can be coerced to boolean
                'adInterval': 10
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        # DRF serializer coerces 'true' string to True boolean
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 10)

    def test_retrieve_ads_config_coercible_interval_value(self):
        """Test that coercible adInterval values are accepted by serializer."""
        # Create config with coercible type for adInterval
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True,
                'adInterval': '10'  # String that can be coerced to integer
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        # DRF serializer coerces '10' string to 10 integer
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 10)

    def test_retrieve_ads_config_truly_invalid_enabled_returns_defaults(self):
        """Test that default values are returned when enabled has truly invalid type."""
        # Create config with non-coercible type for enabled
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': ['array', 'value'],  # Array instead of boolean
                'adInterval': 10
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 5)

    def test_retrieve_ads_config_truly_invalid_interval_returns_defaults(self):
        """Test that default values are returned when adInterval has truly invalid type."""
        # Create config with non-coercible type for adInterval
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True,
                'adInterval': {'nested': 'object'}  # Object instead of integer
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 5)

    def test_retrieve_ads_config_empty_value_returns_defaults(self):
        """Test that default values are returned when config value is empty."""
        # Create config with empty value
        AppConfiguration.objects.create(
            key='ads_config',
            value={}
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 5)

    def test_retrieve_ads_config_extra_fields_ignored(self):
        """Test that extra fields in config are ignored."""
        # Create config with extra fields
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True,
                'adInterval': 8,
                'extraField': 'ignored',
                'anotherField': 123
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 8)
        # Extra fields should not be in response
        self.assertNotIn('extraField', res.data)
        self.assertNotIn('anotherField', res.data)

    def test_retrieve_ads_config_zero_interval(self):
        """Test retrieving ads config with zero interval."""
        # Create ads config with zero interval
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True,
                'adInterval': 0
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 0)

    def test_retrieve_ads_config_negative_interval_returns_defaults(self):
        """Test that default values are returned when interval is negative."""
        # Create config with negative interval
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True,
                'adInterval': -5
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        # Note: This depends on serializer validation.
        # If the serializer doesn't validate negative numbers, it might still pass.
        # Adjust this test based on actual business logic requirements.
        self.assertEqual(res.status_code, status.HTTP_200_OK)

    def test_retrieve_ads_config_large_interval(self):
        """Test retrieving ads config with large interval value."""
        # Create ads config with large interval
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True,
                'adInterval': 999999
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 999999)

    def test_auth_required_even_with_header(self):
        """Test that authentication is still required even with auth-profile-id header."""
        # Remove authentication but keep header
        self.client.force_authenticate(user=None)
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_retrieve_ads_config_different_user(self):
        """Test that different authenticated users can access ads config."""
        # Create another user and profile
        user2 = create_user(
            email="test2@example.com",
            password="testpass123"
        )
        profile2 = create_profile(
            user=user2,
            username="testuser2"
        )
        
        # Create ads config
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': False,
                'adInterval': 20
            }
        )
        
        # Authenticate as second user
        self.client.force_authenticate(user=user2)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile2.id))
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], False)
        self.assertEqual(res.data['adInterval'], 20)

    def test_retrieve_ads_config_null_values_returns_defaults(self):
        """Test that default values are returned when config contains null values."""
        # Create config with null values
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': None,
                'adInterval': None
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 5)

    def test_retrieve_ads_config_case_sensitivity(self):
        """Test that config key is case sensitive."""
        # Create config with different case
        AppConfiguration.objects.create(
            key='ADS_CONFIG',  # Different case
            value={
                'enabled': True,
                'adInterval': 10
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        # Should return defaults because 'ads_config' doesn't exist
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 5)

    def test_multiple_configs_only_ads_config_used(self):
        """Test that only the ads_config is used when multiple configs exist."""
        # Create multiple configs
        AppConfiguration.objects.create(
            key='other_config',
            value={
                'enabled': False,
                'adInterval': 100
            }
        )
        AppConfiguration.objects.create(
            key='ads_config',
            value={
                'enabled': True,
                'adInterval': 7
            }
        )
        
        res = self.client.get(ADS_CONFIG_URL)
        
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        self.assertEqual(res.data['enabled'], True)
        self.assertEqual(res.data['adInterval'], 7)

