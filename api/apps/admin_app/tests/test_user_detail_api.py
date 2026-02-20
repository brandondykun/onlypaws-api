"""
Tests for the admin user detail API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.test_utils.utils import create_user, create_profile, create_profile_image


def get_admin_user_detail_url(user_id):
    """Return admin user detail URL."""
    return reverse("admin-user-detail", kwargs={"pk": user_id})


class PublicAdminUserDetailTests(TestCase):
    """Tests for unauthenticated access to admin user detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.target_user = create_user("target@example.com", "password123")

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_put_returns_401(self):
        """Test that unauthenticated PUT requests return 401."""
        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.put(url, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminUserDetailTests(TestCase):
    """Tests for non-admin authenticated access to admin user detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.target_user = create_user("target@example.com", "password123")
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminUserDetailTests(TestCase):
    """Tests for admin access to the user detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.target_user = create_user("target@example.com", "password123")
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_access_user_detail(self):
        """Test that admin users can access the user detail endpoint."""
        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_required_fields(self):
        """Test that response contains all required fields."""
        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)
        self.assertIn("email", response.data)
        self.assertIn("is_active", response.data)
        self.assertIn("is_staff", response.data)
        self.assertIn("is_superuser", response.data)
        self.assertIn("is_email_verified", response.data)
        self.assertIn("regular_profile_onboarding_completed", response.data)
        self.assertIn("business_profile_onboarding_completed", response.data)
        self.assertIn("last_login", response.data)
        self.assertIn("profiles", response.data)

    def test_only_get_method_allowed(self):
        """Test that only GET method is allowed (RetrieveAPIView)."""
        url = get_admin_user_detail_url(self.target_user.id)

        # POST
        response = self.client.post(url, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PUT
        response = self.client.put(url, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # PATCH
        response = self.client.patch(url, {})
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

        # DELETE
        response = self.client.delete(url)
        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_nonexistent_user_returns_404(self):
        """Test that requesting a nonexistent user returns 404."""
        url = get_admin_user_detail_url(99999)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_correct_user_data(self):
        """Test that the correct user data is returned."""
        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.target_user.id)
        self.assertEqual(response.data["email"], "target@example.com")


class AdminUserDetailProfilesTests(TestCase):
    """Tests for profiles data in user detail response."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.target_user = create_user("target@example.com", "password123")
        self.client.force_authenticate(user=self.admin_user)

    def test_user_with_no_profiles(self):
        """Test user detail response for user with no profiles."""
        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profiles"], [])

    def test_user_with_single_profile(self):
        """Test user detail response for user with single profile."""
        profile = create_profile("target_profile", self.target_user, "About text")

        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["profiles"]), 1)
        
        profile_data = response.data["profiles"][0]
        self.assertEqual(profile_data["id"], profile.id)
        self.assertEqual(profile_data["username"], "target_profile")
        self.assertIn("is_active", profile_data)
        self.assertIn("created_at", profile_data)
        self.assertIn("image", profile_data)
        self.assertIn("profile_type", profile_data)

    def test_user_with_multiple_profiles(self):
        """Test user detail response for user with multiple profiles."""
        profile1 = create_profile("profile_one", self.target_user, "About 1")
        profile2 = create_profile("profile_two", self.target_user, "About 2")

        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["profiles"]), 2)

        usernames = [p["username"] for p in response.data["profiles"]]
        self.assertIn("profile_one", usernames)
        self.assertIn("profile_two", usernames)

    def test_profile_with_image(self):
        """Test that profile image data is included."""
        profile = create_profile("target_profile", self.target_user, "About text")
        create_profile_image(profile)

        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        profile_data = response.data["profiles"][0]
        self.assertIsNotNone(profile_data["image"])

    def test_profile_type_is_regular(self):
        """Test that profile_type is correctly identified as regular."""
        create_profile("target_profile", self.target_user, "About text")

        url = get_admin_user_detail_url(self.target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profiles"][0]["profile_type"], "regular")


class AdminUserDetailStatusFieldsTests(TestCase):
    """Tests for user status fields in detail response."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_inactive_user(self):
        """Test detail response for inactive user."""
        target_user = create_user("inactive@example.com", "password123")
        target_user.is_active = False
        target_user.save()

        url = get_admin_user_detail_url(target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

    def test_staff_user(self):
        """Test detail response for staff user."""
        target_user = create_user("staff@example.com", "password123", is_staff=True)

        url = get_admin_user_detail_url(target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_staff"])

    def test_superuser(self):
        """Test detail response for superuser."""
        target_user = create_user("superuser@example.com", "password123", is_staff=True)
        target_user.is_superuser = True
        target_user.save()

        url = get_admin_user_detail_url(target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_superuser"])

    def test_email_verified_user(self):
        """Test detail response for email verified user."""
        target_user = create_user("verified@example.com", "password123")
        target_user.is_email_verified = True
        target_user.save()

        url = get_admin_user_detail_url(target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_email_verified"])


class AdminUserDetailEdgeCasesTests(TestCase):
    """Edge case tests for admin user detail."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_view_own_details(self):
        """Test that admin can view their own user details."""
        url = get_admin_user_detail_url(self.admin_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "admin@example.com")

    def test_admin_can_view_other_admin(self):
        """Test that admin can view another admin's details."""
        other_admin = create_user("other_admin@example.com", "password123", is_staff=True)

        url = get_admin_user_detail_url(other_admin.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "other_admin@example.com")

    def test_invalid_user_id_format(self):
        """Test that invalid user ID format is handled."""
        url = "/api/admin/users/invalid/"
        response = self.client.get(url)

        # Should return 404 (not found) since invalid ID doesn't match URL pattern
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_profile_with_inactive_status(self):
        """Test user detail includes inactive profile."""
        target_user = create_user("target@example.com", "password123")
        profile = create_profile("target_profile", target_user, "About text")
        profile.is_active = False
        profile.save()

        url = get_admin_user_detail_url(target_user.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["profiles"]), 1)
        self.assertFalse(response.data["profiles"][0]["is_active"])
