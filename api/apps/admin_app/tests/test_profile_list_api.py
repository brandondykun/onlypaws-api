"""
Tests for the admin profile list API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.test_utils.utils import create_user, create_profile, create_profile_image


ADMIN_PROFILE_LIST_URL = reverse("admin-profile-list")


class PublicAdminProfileListTests(TestCase):
    """Tests for unauthenticated access to admin profile list endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_post_returns_401(self):
        """Test that unauthenticated POST requests return 401."""
        response = self.client.post(ADMIN_PROFILE_LIST_URL, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminProfileListTests(TestCase):
    """Tests for non-admin authenticated access to admin profile list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminProfileListTests(TestCase):
    """Tests for admin access to the profile list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_access_profile_list(self):
        """Test that admin users can access the profile list endpoint."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_pagination_fields(self):
        """Test that response contains pagination fields."""
        user = create_user("user@example.com", "password123")
        create_profile("test_user", user, "About")

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_response_contains_required_profile_fields(self):
        """Test that profile objects contain all required fields."""
        user = create_user("user@example.com", "password123")
        create_profile("test_user", user, "About")

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

        profile_data = response.data["results"][0]
        self.assertIn("id", profile_data)
        self.assertIn("username", profile_data)
        self.assertIn("user", profile_data)
        self.assertIn("user_email", profile_data)
        self.assertIn("is_active", profile_data)
        self.assertIn("created_at", profile_data)
        self.assertIn("updated_at", profile_data)
        self.assertIn("image", profile_data)
        self.assertIn("profile_type", profile_data)

    def test_only_get_method_allowed(self):
        """Test that only GET method is allowed."""
        # POST
        response = self.client.post(ADMIN_PROFILE_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT
        response = self.client.put(ADMIN_PROFILE_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH
        response = self.client.patch(ADMIN_PROFILE_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE
        response = self.client.delete(ADMIN_PROFILE_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_lists_all_profiles(self):
        """Test that endpoint lists all profiles."""
        user1 = create_user("user1@example.com", "password123")
        user2 = create_user("user2@example.com", "password123")
        user3 = create_user("user3@example.com", "password123")
        
        create_profile("profile_1", user1, "About 1")
        create_profile("profile_2", user2, "About 2")
        create_profile("profile_3", user3, "About 3")

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)

    def test_empty_profile_list(self):
        """Test response when no profiles exist."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_includes_inactive_profiles(self):
        """Test that inactive profiles are included in the list."""
        user = create_user("user@example.com", "password123")
        profile = create_profile("inactive_profile", user, "About")
        profile.is_active = False
        profile.save()

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertFalse(response.data["results"][0]["is_active"])

    def test_user_email_is_included(self):
        """Test that user_email field is correctly populated."""
        user = create_user("testuser@example.com", "password123")
        create_profile("test_profile", user, "About")

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["user_email"], "testuser@example.com")


class AdminProfileListSearchTests(TestCase):
    """Tests for search functionality in admin profile list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        
        # Create profiles with different usernames
        self.user1 = create_user("user1@example.com", "password123")
        self.user2 = create_user("user2@example.com", "password123")
        self.user3 = create_user("user3@example.com", "password123")
        
        self.profile1 = create_profile("fluffy_cat", self.user1, "About 1")
        self.profile2 = create_profile("doggo_lover", self.user2, "About 2")
        self.profile3 = create_profile("fluffy_bunny", self.user3, "About 3")

    def test_search_by_username_partial_match(self):
        """Test searching profiles by partial username match."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"search": "fluffy"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

        usernames = [p["username"] for p in response.data["results"]]
        self.assertIn("fluffy_cat", usernames)
        self.assertIn("fluffy_bunny", usernames)

    def test_search_by_username_exact_match(self):
        """Test searching profiles by exact username."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"search": "doggo_lover"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["username"], "doggo_lover")

    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"search": "FLUFFY"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)

    def test_search_no_results(self):
        """Test search with no matching results."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"search": "nonexistent"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_search_empty_string_returns_all(self):
        """Test that empty search string returns all profiles."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"search": ""})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 3)


class AdminProfileListOrderingTests(TestCase):
    """Tests for ordering functionality in admin profile list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        
        self.user_a = create_user("user_a@example.com", "password123")
        self.user_b = create_user("user_b@example.com", "password123")
        self.user_c = create_user("user_c@example.com", "password123")
        
        self.profile_z = create_profile("zebra", self.user_a, "About")
        self.profile_a = create_profile("aardvark", self.user_b, "About")
        self.profile_m = create_profile("monkey", self.user_c, "About")

    def test_default_ordering_by_id(self):
        """Test that default ordering is by id."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [p["id"] for p in response.data["results"]]
        self.assertEqual(ids, sorted(ids))

    def test_ordering_by_username_ascending(self):
        """Test ordering profiles by username ascending."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"ordering": "username"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [p["username"] for p in response.data["results"]]
        self.assertEqual(usernames, sorted(usernames))

    def test_ordering_by_username_descending(self):
        """Test ordering profiles by username descending."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"ordering": "-username"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        usernames = [p["username"] for p in response.data["results"]]
        self.assertEqual(usernames, sorted(usernames, reverse=True))

    def test_ordering_by_is_active(self):
        """Test ordering profiles by is_active status."""
        self.profile_a.is_active = False
        self.profile_a.save()

        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"ordering": "is_active"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Inactive profile (False) should come first
        self.assertFalse(response.data["results"][0]["is_active"])

    def test_ordering_by_created_at(self):
        """Test ordering profiles by created_at."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"ordering": "-created_at"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Most recently created should be first
        self.assertEqual(response.data["results"][0]["username"], "monkey")


class AdminProfileListPaginationTests(TestCase):
    """Tests for pagination in admin profile list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_default_page_size(self):
        """Test that default page size is 25."""
        # Create 30 profiles
        for i in range(30):
            user = create_user(f"user{i}@example.com", "password123")
            create_profile(f"profile_{i}", user, f"About {i}")

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 30)
        self.assertEqual(len(response.data["results"]), 25)
        self.assertIsNotNone(response.data["next"])

    def test_custom_page_size(self):
        """Test custom page_size parameter."""
        for i in range(15):
            user = create_user(f"user{i}@example.com", "password123")
            create_profile(f"profile_{i}", user, f"About {i}")

        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)

    def test_page_size_max_limit(self):
        """Test that page_size respects max limit of 100."""
        for i in range(105):
            user = create_user(f"user{i}@example.com", "password123")
            create_profile(f"profile_{i}", user, f"About {i}")

        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"page_size": 200})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be capped at 100
        self.assertEqual(len(response.data["results"]), 100)

    def test_pagination_second_page(self):
        """Test accessing the second page of results."""
        for i in range(30):
            user = create_user(f"user{i}@example.com", "password123")
            create_profile(f"profile_{i}", user, f"About {i}")

        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"page": 2, "page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["previous"])

    def test_invalid_page_returns_404(self):
        """Test that requesting an invalid page returns 404."""
        response = self.client.get(ADMIN_PROFILE_LIST_URL, {"page": 999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminProfileListEdgeCasesTests(TestCase):
    """Edge case tests for admin profile list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_profile_with_image(self):
        """Test that profile image data is included."""
        user = create_user("user@example.com", "password123")
        profile = create_profile("test_profile", user, "About")
        create_profile_image(profile)

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["results"][0]["image"])

    def test_profile_without_image(self):
        """Test that profile without image has null image field."""
        user = create_user("user@example.com", "password123")
        create_profile("test_profile", user, "About")

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["results"][0]["image"])

    def test_multiple_profiles_same_user(self):
        """Test that multiple profiles from same user are listed."""
        user = create_user("user@example.com", "password123")
        create_profile("profile_1", user, "About 1")
        create_profile("profile_2", user, "About 2")

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 2)
        
        # Both should have same user_email
        emails = set(p["user_email"] for p in response.data["results"])
        self.assertEqual(len(emails), 1)
        self.assertEqual(list(emails)[0], "user@example.com")

    def test_profile_type_is_regular(self):
        """Test that profile_type is correctly identified as regular."""
        user = create_user("user@example.com", "password123")
        create_profile("test_profile", user, "About")

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["results"][0]["profile_type"], "regular")

    def test_superuser_can_access(self):
        """Test that superusers can also access the endpoint."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()
        
        self.client.force_authenticate(user=superuser)
        
        user = create_user("user@example.com", "password123")
        create_profile("test_profile", user, "About")

        response = self.client.get(ADMIN_PROFILE_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
