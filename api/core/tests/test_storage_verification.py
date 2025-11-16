"""
Quick test to verify in-memory storage is working correctly.
Run this with: python manage.py test core.tests.test_storage_verification
"""

from django.test import TestCase
from django.core.files.storage import default_storage
from apps.posts_app.models import Post, PostImage
from core.test_utils.utils import create_user, create_profile, create_test_image


class InMemoryStorageVerificationTest(TestCase):
    """Verify that in-memory storage is working correctly during tests."""

    def test_storage_backend_is_in_memory(self):
        """Verify that the default storage backend is InMemoryStorage."""
        from core.storage import InMemoryStorage
        self.assertIsInstance(default_storage, InMemoryStorage)

    def test_images_stay_in_memory(self):
        """Verify that images created during tests don't write to disk."""
        # Create a post with an image
        user = create_user("test@example.com", "testpass123")
        profile = create_profile("testuser", user)
        post = Post.objects.create(caption="Test post", profile=profile)
        
        # Create an image
        test_image = create_test_image('verification_test.jpg')
        post_image = PostImage.objects.create(post=post, image=test_image)
        
        # Verify the image exists in storage
        self.assertTrue(default_storage.exists(post_image.image.name))
        
        # Verify we can open and read the image
        with default_storage.open(post_image.image.name) as f:
            content = f.read()
            self.assertIsNotNone(content)
            self.assertGreater(len(content), 0)
        
        # Verify the storage is InMemoryStorage
        from core.storage import InMemoryStorage
        self.assertIn(post_image.image.name, InMemoryStorage._files)
        
    def test_storage_clear_works(self):
        """Verify that storage.clear() removes all files from memory."""
        from core.storage import InMemoryStorage
        
        # Create a test image
        user = create_user("test2@example.com", "testpass123")
        profile = create_profile("testuser2", user)
        post = Post.objects.create(caption="Test post 2", profile=profile)
        
        test_image = create_test_image('clear_test.jpg')
        post_image = PostImage.objects.create(post=post, image=test_image)
        
        # Verify image exists
        self.assertTrue(default_storage.exists(post_image.image.name))
        self.assertGreater(len(InMemoryStorage._files), 0)
        
        # Clear storage
        InMemoryStorage.clear()
        
        # Verify all files are cleared
        self.assertEqual(len(InMemoryStorage._files), 0)
        self.assertFalse(default_storage.exists(post_image.image.name))

