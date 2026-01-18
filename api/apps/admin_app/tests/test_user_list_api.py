"""
Tests for the admin user list API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.test_utils.utils import create_user, create_profile


ADMIN_USER_LIST_URL = reverse("admin-user-list")


class PublicAdminUserListTests(TestCase):
    """Tests for unauthenticated access to admin user list endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_post_returns_401(self):
        """Test that unauthenticated POST requests return 401."""
        response = self.client.post(ADMIN_USER_LIST_URL, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminUserListTests(TestCase):
    """Tests for non-admin authenticated access to admin user list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=profile.id)

        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminUserListTests(TestCase):
    """Tests for admin access to the user list endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_access_user_list(self):
        """Test that admin users can access the user list endpoint."""
        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_pagination_fields(self):
        """Test that response contains pagination fields."""
        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("count", response.data)
        self.assertIn("next", response.data)
        self.assertIn("previous", response.data)
        self.assertIn("results", response.data)

    def test_response_contains_required_user_fields(self):
        """Test that user objects contain all required fields."""
        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 1)

        user_data = response.data["results"][0]
        self.assertIn("id", user_data)
        self.assertIn("email", user_data)
        self.assertIn("is_active", user_data)
        self.assertIn("is_staff", user_data)
        self.assertIn("is_email_verified", user_data)
        self.assertIn("regular_profile_onboarding_completed", user_data)
        self.assertIn("business_profile_onboarding_completed", user_data)
        self.assertIn("profiles_count", user_data)

    def test_only_get_method_allowed(self):
        """Test that only GET method is allowed."""
        # POST
        response = self.client.post(ADMIN_USER_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT
        response = self.client.put(ADMIN_USER_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH
        response = self.client.patch(ADMIN_USER_LIST_URL, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE
        response = self.client.delete(ADMIN_USER_LIST_URL)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_lists_all_users(self):
        """Test that endpoint lists all users."""
        create_user("user1@example.com", "password123")
        create_user("user2@example.com", "password123")
        create_user("user3@example.com", "password123")

        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin + 3 regular users = 4
        self.assertEqual(response.data["count"], 4)

    def test_includes_inactive_users(self):
        """Test that inactive users are included in the list."""
        active_user = create_user("active@example.com", "password123")
        inactive_user = create_user("inactive@example.com", "password123")
        inactive_user.is_active = False
        inactive_user.save()

        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin + 2 users = 3
        self.assertEqual(response.data["count"], 3)

        emails = [u["email"] for u in response.data["results"]]
        self.assertIn("inactive@example.com", emails)

    def test_profiles_count_is_correct(self):
        """Test that profiles_count field is correct."""
        user = create_user("user@example.com", "password123")
        create_profile("profile_1", user, "About 1")
        create_profile("profile_2", user, "About 2")

        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_data = next(
            u for u in response.data["results"] if u["email"] == "user@example.com"
        )
        self.assertEqual(user_data["profiles_count"], 2)


class AdminUserListSearchTests(TestCase):
    """Tests for search functionality in admin user list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        
        # Create users with different emails
        self.user1 = create_user("john.doe@example.com", "password123")
        self.user2 = create_user("jane.smith@example.com", "password123")
        self.user3 = create_user("bob.wilson@test.com", "password123")

    def test_search_by_email_partial_match(self):
        """Test searching users by partial email match."""
        response = self.client.get(ADMIN_USER_LIST_URL, {"search": "example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin + john + jane = 3 (bob has test.com)
        self.assertEqual(response.data["count"], 3)

    def test_search_by_email_exact_match(self):
        """Test searching users by exact email."""
        response = self.client.get(ADMIN_USER_LIST_URL, {"search": "john.doe@example.com"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "john.doe@example.com")

    def test_search_case_insensitive(self):
        """Test that search is case insensitive."""
        response = self.client.get(ADMIN_USER_LIST_URL, {"search": "JOHN"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 1)
        self.assertEqual(response.data["results"][0]["email"], "john.doe@example.com")

    def test_search_no_results(self):
        """Test search with no matching results."""
        response = self.client.get(ADMIN_USER_LIST_URL, {"search": "nonexistent"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 0)
        self.assertEqual(len(response.data["results"]), 0)

    def test_search_empty_string_returns_all(self):
        """Test that empty search string returns all users."""
        response = self.client.get(ADMIN_USER_LIST_URL, {"search": ""})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin + 3 users = 4
        self.assertEqual(response.data["count"], 4)


class AdminUserListOrderingTests(TestCase):
    """Tests for ordering functionality in admin user list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        
        self.user_a = create_user("alice@example.com", "password123")
        self.user_b = create_user("bob@example.com", "password123")
        self.user_c = create_user("charlie@example.com", "password123")

    def test_default_ordering_by_id(self):
        """Test that default ordering is by id."""
        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        ids = [u["id"] for u in response.data["results"]]
        self.assertEqual(ids, sorted(ids))

    def test_ordering_by_email_ascending(self):
        """Test ordering users by email ascending."""
        response = self.client.get(ADMIN_USER_LIST_URL, {"ordering": "email"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [u["email"] for u in response.data["results"]]
        self.assertEqual(emails, sorted(emails))

    def test_ordering_by_email_descending(self):
        """Test ordering users by email descending."""
        response = self.client.get(ADMIN_USER_LIST_URL, {"ordering": "-email"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [u["email"] for u in response.data["results"]]
        self.assertEqual(emails, sorted(emails, reverse=True))

    def test_ordering_by_is_active(self):
        """Test ordering users by is_active status."""
        # Make one user inactive
        self.user_a.is_active = False
        self.user_a.save()

        response = self.client.get(ADMIN_USER_LIST_URL, {"ordering": "is_active"})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Inactive user (False) should come first
        self.assertFalse(response.data["results"][0]["is_active"])


class AdminUserListPaginationTests(TestCase):
    """Tests for pagination in admin user list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_default_page_size(self):
        """Test that default page size is 25."""
        # Create 30 users total (admin + 29 more)
        for i in range(29):
            create_user(f"user{i}@example.com", "password123")

        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["count"], 30)
        self.assertEqual(len(response.data["results"]), 25)
        self.assertIsNotNone(response.data["next"])

    def test_custom_page_size(self):
        """Test custom page_size parameter."""
        for i in range(15):
            create_user(f"user{i}@example.com", "password123")

        response = self.client.get(ADMIN_USER_LIST_URL, {"page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)

    def test_page_size_max_limit(self):
        """Test that page_size respects max limit of 100."""
        for i in range(105):
            create_user(f"user{i}@example.com", "password123")

        response = self.client.get(ADMIN_USER_LIST_URL, {"page_size": 200})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Should be capped at 100
        self.assertEqual(len(response.data["results"]), 100)

    def test_pagination_second_page(self):
        """Test accessing the second page of results."""
        for i in range(30):
            create_user(f"user{i}@example.com", "password123")

        response = self.client.get(ADMIN_USER_LIST_URL, {"page": 2, "page_size": 10})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["results"]), 10)
        self.assertIsNotNone(response.data["previous"])

    def test_invalid_page_returns_404(self):
        """Test that requesting an invalid page returns 404."""
        response = self.client.get(ADMIN_USER_LIST_URL, {"page": 999})

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)


class AdminUserListEdgeCasesTests(TestCase):
    """Edge case tests for admin user list."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_user_with_no_profiles(self):
        """Test that users with no profiles are included."""
        user = create_user("noprofile@example.com", "password123")

        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_data = next(
            u for u in response.data["results"] if u["email"] == "noprofile@example.com"
        )
        self.assertEqual(user_data["profiles_count"], 0)

    def test_user_with_multiple_profiles(self):
        """Test profiles_count for user with multiple profiles."""
        user = create_user("multiprofile@example.com", "password123")
        create_profile("profile1", user, "About 1")
        create_profile("profile2", user, "About 2")
        create_profile("profile3", user, "About 3")

        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        user_data = next(
            u for u in response.data["results"] if u["email"] == "multiprofile@example.com"
        )
        self.assertEqual(user_data["profiles_count"], 3)

    def test_staff_users_are_included(self):
        """Test that staff users are included in the list."""
        staff_user = create_user("staff@example.com", "password123", is_staff=True)

        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        emails = [u["email"] for u in response.data["results"]]
        self.assertIn("staff@example.com", emails)

    def test_superuser_can_access(self):
        """Test that superusers can also access the endpoint."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()
        
        self.client.force_authenticate(user=superuser)

        response = self.client.get(ADMIN_USER_LIST_URL)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
