"""
Tests for the admin profile detail API endpoint.
"""

from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status

from core.test_utils.utils import (
    create_user,
    create_profile,
    create_profile_image,
    create_post,
    create_follow,
    create_pet_type,
)


def get_admin_profile_detail_url(profile_id):
    """Return admin profile detail URL."""
    return reverse("admin-profile-detail", kwargs={"pk": profile_id})


class PublicAdminProfileDetailTests(TestCase):
    """Tests for unauthenticated access to admin profile detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.user = create_user("user@example.com", "password123")
        self.profile = create_profile("target_profile", self.user, "About")

    def test_unauthenticated_user_returns_401(self):
        """Test that unauthenticated requests return 401."""
        url = get_admin_profile_detail_url(self.profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_unauthenticated_put_returns_401(self):
        """Test that unauthenticated PUT requests return 401."""
        url = get_admin_profile_detail_url(self.profile.id)
        response = self.client.put(url, {})

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class NonAdminProfileDetailTests(TestCase):
    """Tests for non-admin authenticated access to admin profile detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.regular_user = create_user("regular@example.com", "password123", is_staff=False)
        self.target_user = create_user("target@example.com", "password123")
        self.target_profile = create_profile("target_profile", self.target_user, "About")
        self.client.force_authenticate(user=self.regular_user)

    def test_non_admin_user_returns_403(self):
        """Test that authenticated non-admin users receive 403."""
        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_non_admin_user_with_profile_returns_403(self):
        """Test that authenticated non-admin users with profile receive 403."""
        profile = create_profile("regular_profile", self.regular_user, "About me")
        self.client.credentials(HTTP_AUTH_PROFILE_ID=profile.id)

        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class AdminProfileDetailTests(TestCase):
    """Tests for admin access to the profile detail endpoint."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.target_user = create_user("target@example.com", "password123")
        self.target_profile = create_profile("target_profile", self.target_user, "About text", name="Target Name")
        self.client.force_authenticate(user=self.admin_user)

    def test_admin_can_access_profile_detail(self):
        """Test that admin users can access the profile detail endpoint."""
        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_response_contains_required_fields(self):
        """Test that response contains all required fields."""
        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("id", response.data)
        self.assertIn("username", response.data)
        self.assertIn("user_id", response.data)
        self.assertIn("user_email", response.data)
        self.assertIn("name", response.data)
        self.assertIn("about", response.data)
        self.assertIn("breed", response.data)
        self.assertIn("pet_type", response.data)
        self.assertIn("image", response.data)
        self.assertIn("is_active", response.data)
        self.assertIn("created_at", response.data)
        self.assertIn("updated_at", response.data)
        self.assertIn("posts_count", response.data)
        self.assertIn("followers_count", response.data)
        self.assertIn("following_count", response.data)
        self.assertIn("profile_type", response.data)

    def test_only_get_method_allowed(self):
        """Test that only GET method is allowed (RetrieveAPIView)."""
        url = get_admin_profile_detail_url(self.target_profile.id)

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

    def test_nonexistent_profile_returns_404(self):
        """Test that requesting a nonexistent profile returns 404."""
        url = get_admin_profile_detail_url(99999)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_returns_correct_profile_data(self):
        """Test that the correct profile data is returned."""
        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["id"], self.target_profile.id)
        self.assertEqual(response.data["username"], "target_profile")
        self.assertEqual(response.data["user_email"], "target@example.com")
        self.assertEqual(response.data["about"], "About text")
        self.assertEqual(response.data["name"], "Target Name")


class AdminProfileDetailStatsTests(TestCase):
    """Tests for profile stats in detail response."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.target_user = create_user("target@example.com", "password123")
        self.target_profile = create_profile("target_profile", self.target_user, "About")
        self.client.force_authenticate(user=self.admin_user)

    def test_posts_count_zero(self):
        """Test posts_count is zero for profile with no posts."""
        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["posts_count"], 0)

    def test_posts_count_correct(self):
        """Test posts_count is correct for profile with posts."""
        create_post("Post 1", self.target_profile)
        create_post("Post 2", self.target_profile)
        create_post("Post 3", self.target_profile)

        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["posts_count"], 3)

    def test_followers_count_zero(self):
        """Test followers_count is zero for profile with no followers."""
        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["followers_count"], 0)

    def test_followers_count_correct(self):
        """Test followers_count is correct."""
        # Create other profiles that follow target_profile
        user1 = create_user("user1@example.com", "password123")
        user2 = create_user("user2@example.com", "password123")
        profile1 = create_profile("follower_1", user1, "About")
        profile2 = create_profile("follower_2", user2, "About")

        create_follow(profile1, self.target_profile)
        create_follow(profile2, self.target_profile)

        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["followers_count"], 2)

    def test_following_count_zero(self):
        """Test following_count is zero for profile not following anyone."""
        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["following_count"], 0)

    def test_following_count_correct(self):
        """Test following_count is correct."""
        # Create profiles that target_profile follows
        user1 = create_user("user1@example.com", "password123")
        user2 = create_user("user2@example.com", "password123")
        profile1 = create_profile("followed_1", user1, "About")
        profile2 = create_profile("followed_2", user2, "About")

        create_follow(self.target_profile, profile1)
        create_follow(self.target_profile, profile2)

        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["following_count"], 2)


class AdminProfileDetailImageTests(TestCase):
    """Tests for profile image in detail response."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.target_user = create_user("target@example.com", "password123")
        self.target_profile = create_profile("target_profile", self.target_user, "About")
        self.client.force_authenticate(user=self.admin_user)

    def test_profile_without_image(self):
        """Test that profile without image has null image field."""
        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["image"])

    def test_profile_with_image(self):
        """Test that profile image data is included."""
        create_profile_image(self.target_profile)

        url = get_admin_profile_detail_url(self.target_profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["image"])


class AdminProfileDetailStatusTests(TestCase):
    """Tests for profile status fields in detail response."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_active_profile(self):
        """Test detail response for active profile."""
        user = create_user("user@example.com", "password123")
        profile = create_profile("active_profile", user, "About")

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_active"])

    def test_inactive_profile(self):
        """Test detail response for inactive profile."""
        user = create_user("user@example.com", "password123")
        profile = create_profile("inactive_profile", user, "About")
        profile.is_active = False
        profile.save()

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["is_active"])

    def test_profile_type_regular(self):
        """Test that profile_type is correctly identified as regular."""
        user = create_user("user@example.com", "password123")
        profile = create_profile("regular_profile", user, "About")

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["profile_type"], "regular")


class AdminProfileDetailPetFieldsTests(TestCase):
    """Tests for pet-specific fields in profile detail response."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_profile_with_pet_type(self):
        """Test that profile with pet_type returns serialized pet_type data."""
        user = create_user("user@example.com", "password123")
        pet_type = create_pet_type("Dog")
        profile = create_profile("pet_profile", user, "About my dog", pet_type=pet_type)

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNotNone(response.data["pet_type"])
        self.assertEqual(response.data["pet_type"]["name"], "Dog")

    def test_profile_without_pet_type(self):
        """Test that profile without pet_type returns null."""
        user = create_user("user@example.com", "password123")
        profile = create_profile("no_pet_type", user, "About")

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIsNone(response.data["pet_type"])

    def test_profile_with_breed(self):
        """Test that profile with breed returns breed value."""
        user = create_user("user@example.com", "password123")
        profile = create_profile(
            "breed_profile",
            user,
            "About my golden retriever",
            breed="Golden Retriever"
        )

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["breed"], "Golden Retriever")

    def test_profile_without_breed(self):
        """Test that profile without breed returns empty string."""
        user = create_user("user@example.com", "password123")
        profile = create_profile("no_breed", user, "About")

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["breed"], "")

    def test_profile_with_all_pet_fields(self):
        """Test that profile with all pet fields returns correct data."""
        user = create_user("user@example.com", "password123")
        pet_type = create_pet_type("Cat")
        profile = create_profile(
            "full_pet_profile",
            user,
            "About my cat Whiskers",
            name="Whiskers",
            pet_type=pet_type,
            breed="Persian"
        )

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["name"], "Whiskers")
        self.assertEqual(response.data["about"], "About my cat Whiskers")
        self.assertEqual(response.data["pet_type"]["name"], "Cat")
        self.assertEqual(response.data["breed"], "Persian")

    def test_different_pet_types(self):
        """Test profiles with different pet types."""
        user1 = create_user("user1@example.com", "password123")
        user2 = create_user("user2@example.com", "password123")
        
        dog_type = create_pet_type("Dog")
        cat_type = create_pet_type("Cat")
        
        dog_profile = create_profile("dog_lover", user1, "About", pet_type=dog_type)
        cat_profile = create_profile("cat_lover", user2, "About", pet_type=cat_type)

        # Check dog profile
        url = get_admin_profile_detail_url(dog_profile.id)
        response = self.client.get(url)
        self.assertEqual(response.data["pet_type"]["name"], "Dog")

        # Check cat profile
        url = get_admin_profile_detail_url(cat_profile.id)
        response = self.client.get(url)
        self.assertEqual(response.data["pet_type"]["name"], "Cat")


class AdminProfileDetailEdgeCasesTests(TestCase):
    """Edge case tests for admin profile detail."""

    def setUp(self):
        self.client = APIClient()
        self.admin_user = create_user("admin@example.com", "admin_password_123", is_staff=True)
        self.client.force_authenticate(user=self.admin_user)

    def test_profile_of_inactive_user(self):
        """Test detail response for profile of inactive user."""
        user = create_user("inactive@example.com", "password123")
        user.is_active = False
        user.save()
        profile = create_profile("test_profile", user, "About")

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["user_email"], "inactive@example.com")

    def test_invalid_profile_id_format(self):
        """Test that invalid profile ID format is handled."""
        url = "/api/admin/profiles/invalid/"
        response = self.client.get(url)

        # Should return 404 (not found) since invalid ID doesn't match URL pattern
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_profile_with_empty_fields(self):
        """Test profile with empty optional fields."""
        user = create_user("user@example.com", "password123")
        profile = create_profile("minimal_profile", user, "")

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["about"], "")

    def test_superuser_can_access(self):
        """Test that superusers can also access the endpoint."""
        superuser = create_user("superuser@example.com", "password123", is_staff=True)
        superuser.is_superuser = True
        superuser.save()
        
        self.client.force_authenticate(user=superuser)
        
        user = create_user("user@example.com", "password123")
        profile = create_profile("test_profile", user, "About")

        url = get_admin_profile_detail_url(profile.id)
        response = self.client.get(url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
