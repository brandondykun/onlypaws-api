"""
Tests for the search profiles api.
"""

from rest_framework import status
from django.db.models import Q

from apps.profile_app.models import Profile
from .util import search_profiles_url
from core.test_utils.utils import create_user, create_profile
from core.test_utils.helper_classes import BaseFixtureTestCase


class PrivateSearchProfilesApiTests(BaseFixtureTestCase):
    """Test the private features of the search profiles API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # create fourth user and profile - this profile username should not contain "user"
        self.user_5 = create_user("test5@example.com", "user5-password-123")
        self.profile_5 = create_profile("different", self.user_5,"Test about text.")
        # extend setUp by authenticating self.profile
        self.client.force_authenticate(user=self.user)
        self.client.credentials(HTTP_AUTH_PROFILE_ID=self.profile.id)

    def test_search_profiles_successful(self):
        """
        Test searching for profiles by username returns results
        that match the searched username text.
        """
        search_text = "user"
        url = search_profiles_url("user")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        match_count = len(
            Profile.objects.filter(
                Q(username__icontains=search_text) & ~Q(id=self.profile.id)
            )
        )
        self.assertEqual(len(res.data["results"]), match_count)

    def test_search_profiles_without_username_returns_error(self):
        """
        Test searching for profiles by username but not
        providing a username returns error.
        """
        url = search_profiles_url("")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)


class PublicSearchProfilesApiTests(BaseFixtureTestCase):
    """Test the public features of the search profiles API."""

    def setUp(self):
        super(self.__class__, self).setUp()
        # do not extend setUp therefore not authenticating a profile

    def test_search_profiles_without_authentication_returns_error(self):
        """
        Test searching for profiles by username without
        authentication returns error.
        """
        url = search_profiles_url("user")
        res = self.client.get(url)
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

