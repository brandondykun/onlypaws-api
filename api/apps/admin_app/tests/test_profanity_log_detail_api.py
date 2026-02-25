"""
Tests for the admin profanity log detail API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from apps.moderation_app.models import ProfanityLog
from apps.profile_app.models import Profile
from core.test_utils.utils import create_user, create_profile, create_profanity_log


def get_admin_profanity_log_detail_url(log_id):
    """Return admin profanity log detail URL."""
    return reverse("admin-profanity-log-detail", kwargs={"pk": log_id})


class PublicAdminProfanityLogDetailTests(TestCase):
    """Tests for unauthenticated access to admin profanity log detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.log = create_profanity_log("bad word")

    def test_unauthenticated_get_returns_401(self):
        """Test that unauthenticated GET requests return 401."""
        url = get_admin_profanity_log_detail_url(self.log.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_delete_returns_401(self):
        """Test that unauthenticated DELETE requests return 401."""
        url = get_admin_profanity_log_detail_url(self.log.id)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminProfanityLogDetailTests(TestCase):
    """Tests for non-admin authenticated access to admin profanity log detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.log = create_profanity_log("bad word")
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        url = get_admin_profanity_log_detail_url(self.log.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_user", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=str(profile.public_id))

        url = get_admin_profanity_log_detail_url(self.log.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminProfanityLogDetailGetTests(TestCase):
    """Tests for GET requests to admin profanity log detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)
        self.log = create_profanity_log(
            "offensive text here",
            content_type="COMMENT",
            detection_method="WORD_MATCH",
            detection_details={"matched_word": "offensive"},
        )

    def test_admin_can_retrieve_profanity_log(self):
        """Test that admin users can retrieve profanity log details."""
        url = get_admin_profanity_log_detail_url(self.log.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_required_fields(self):
        """Test that response contains all required fields."""
        url = get_admin_profanity_log_detail_url(self.log.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)
        self.assertIn("original_text", response.data)
        self.assertIn("content_type", response.data)
        self.assertIn("detection_method", response.data)
        self.assertIn("detection_details", response.data)
        self.assertIn("profile", response.data)
        self.assertIn("profile_username", response.data)
        self.assertIn("created_at", response.data)

    def test_returns_correct_profanity_log_data(self):
        """Test that the correct profanity log data is returned."""
        url = get_admin_profanity_log_detail_url(self.log.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.log.id)
        self.assertEqual(response.data["original_text"], "offensive text here")
        self.assertEqual(response.data["content_type"], "COMMENT")
        self.assertEqual(response.data["detection_method"], "WORD_MATCH")
        self.assertEqual(response.data["detection_details"], {"matched_word": "offensive"})

    def test_nonexistent_log_returns_404(self):
        """Test that requesting a nonexistent profanity log returns 404."""
        url = get_admin_profanity_log_detail_url(99999)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_log_with_profile_shows_username(self):
        """Test that log linked to a profile shows the profile username."""
        user = create_user("loguser@example.com", "password123")
        profile = create_profile("log_profile", user)
        log = create_profanity_log("bad word", profile=profile)

        url = get_admin_profanity_log_detail_url(log.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile_username"], "log_profile")

    def test_log_without_profile_shows_null(self):
        """Test that log without a profile shows null profile and profile_username."""
        log = create_profanity_log("bad word", profile=None)

        url = get_admin_profanity_log_detail_url(log.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["profile"])
        self.assertIsNone(response.data["profile_username"])


class AdminProfanityLogDetailDeleteTests(TestCase):
    """Tests for DELETE requests to admin profanity log detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_delete_profanity_log(self):
        """Test that admin users can delete profanity logs."""
        log = create_profanity_log("to delete")
        url = get_admin_profanity_log_detail_url(log.id)

        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Verify log is deleted
        response = self.client.get(url)
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_nonexistent_log_returns_404(self):
        """Test that deleting a nonexistent profanity log returns 404."""
        url = get_admin_profanity_log_detail_url(99999)
        response = self.client.delete(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_delete_removes_from_list(self):
        """Test that deleted profanity log no longer appears in list."""
        log = create_profanity_log("to delete")
        log_id = log.id

        url = get_admin_profanity_log_detail_url(log_id)
        self.client.delete(url)

        list_url = reverse("admin-profanity-log-list")
        response = self.client.get(list_url)

        ids = [entry["id"] for entry in response.data["results"]]
        self.assertNotIn(log_id, ids)

    def test_delete_with_profile_does_not_cascade(self):
        """Test that deleting a profanity log does not delete the associated profile."""
        user = create_user("cascade@example.com", "password123")
        profile = create_profile("cascade_profile", user)
        log = create_profanity_log("bad word", profile=profile)
        profile_id = profile.id

        url = get_admin_profanity_log_detail_url(log.id)
        self.client.delete(url)

        # Profile should still exist
        self.assertTrue(Profile.objects.filter(id=profile_id).exists())


class AdminProfanityLogDetailEdgeCasesTests(TestCase):
    """Edge case tests for admin profanity log detail."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_put_method_not_allowed(self):
        """Test that PUT method returns 405."""
        log = create_profanity_log("test")
        url = get_admin_profanity_log_detail_url(log.id)
        response = self.client.put(url, {})

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_patch_method_not_allowed(self):
        """Test that PATCH method returns 405."""
        log = create_profanity_log("test")
        url = get_admin_profanity_log_detail_url(log.id)
        response = self.client.patch(url, {})

        self.assertEqual(response.status_code, status.HTTP_405_METHOD_NOT_ALLOWED)

    def test_superuser_can_access(self):
        """Test that superusers can access the endpoint."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()

        self.client.force_authenticate(user=superuser)

        log = create_profanity_log("test")
        url = get_admin_profanity_log_detail_url(log.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)


class AdminProfanityLogDetailContentTypeTests(TestCase):
    """Tests for retrieving logs with different content types."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_all_content_types_retrievable(self):
        """Test that logs for each ContentType can be retrieved."""
        content_types = [
            "CAPTION", "COMMENT", "USERNAME", "ABOUT",
            "NAME", "BREED", "PRE_UPLOAD_CHECK",
        ]
        for ct in content_types:
            log = create_profanity_log(f"text for {ct}", content_type=ct)
            url = get_admin_profanity_log_detail_url(log.id)
            response = self.client.get(url)

            self.assertEqual(response.status_code, status.HTTP_200_OK)
            self.assertEqual(response.data["content_type"], ct)
