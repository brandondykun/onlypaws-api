from django.test import TestCase
from django.urls import reverse
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from apps.user_app.models import RegularProfile
from apps.posts_app.models import Post
from apps.notifications_app.models import Notification, NotificationType

User = get_user_model()


class NotificationAPITestCase(TestCase):
    """Test case for notification API endpoints."""
    
    def setUp(self):
        """Set up test data."""
        # Create users and profiles
        self.user1 = User.objects.create_user(
            email="user1@example.com",
            password="testpass123"
        )
        self.user2 = User.objects.create_user(
            email="user2@example.com", 
            password="testpass123"
        )
        
        self.profile1 = RegularProfile.objects.create(
            user=self.user1,
            username="user1",
            name="User One"
        )
        self.profile2 = RegularProfile.objects.create(
            user=self.user2,
            username="user2",
            name="User Two"
        )
        
        # Create a post
        self.post = Post.objects.create(
            caption="Test post",
            profile=self.profile1
        )
        
        # Set up API client
        self.client = APIClient()
        
        # Get JWT token for authentication
        refresh = RefreshToken.for_user(self.user1)
        self.access_token = str(refresh.access_token)
    
    def authenticate(self, profile_id):
        """Authenticate the client with JWT token and profile ID."""
        self.client.credentials(
            HTTP_AUTHORIZATION=f'Bearer {self.access_token}',
            HTTP_AUTH_PROFILE_ID=str(profile_id)
        )
    
    def test_create_notification(self):
        """Test creating a notification."""
        notification = Notification.objects.create(
            recipient=self.profile1,
            sender=self.profile2,
            notification_type=NotificationType.LIKE_POST,
            title="Test notification",
            message="This is a test notification",
            post=self.post
        )
        
        self.assertEqual(notification.recipient, self.profile1)
        self.assertEqual(notification.sender, self.profile2)
        self.assertEqual(notification.notification_type, NotificationType.LIKE_POST)
        self.assertFalse(notification.is_read)
    
    def test_list_notifications(self):
        """Test listing notifications for a profile."""
        # Create a notification
        Notification.objects.create(
            recipient=self.profile1,
            sender=self.profile2,
            notification_type=NotificationType.LIKE_POST,
            title="Test notification",
            message="This is a test notification",
            post=self.post
        )
        
        self.authenticate(self.profile1.id)
        url = reverse('notifications_app:list_notifications')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], "Test notification")
    
    def test_list_unread_notifications(self):
        """Test listing only unread notifications."""
        # Create read and unread notifications
        Notification.objects.create(
            recipient=self.profile1,
            sender=self.profile2,
            notification_type=NotificationType.LIKE_POST,
            title="Read notification",
            message="This notification is read",
            post=self.post,
            is_read=True
        )
        Notification.objects.create(
            recipient=self.profile1,
            sender=self.profile2,
            notification_type=NotificationType.LIKE_POST,
            title="Unread notification",
            message="This notification is unread",
            post=self.post,
            is_read=False
        )
        
        self.authenticate(self.profile1.id)
        url = reverse('notifications_app:list_unread_notifications')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 1)
        self.assertEqual(response.data['results'][0]['title'], "Unread notification")
    
    def test_mark_notification_as_read(self):
        """Test marking a notification as read."""
        notification = Notification.objects.create(
            recipient=self.profile1,
            sender=self.profile2,
            notification_type=NotificationType.LIKE_POST,
            title="Test notification",
            message="This is a test notification",
            post=self.post,
            is_read=False
        )
        
        self.authenticate(self.profile1.id)
        url = reverse('notifications_app:retrieve_update_notification', args=[notification.id])
        response = self.client.patch(url, {'is_read': True})
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
    
    def test_get_notification_counts(self):
        """Test getting notification counts."""
        # Create notifications
        Notification.objects.create(
            recipient=self.profile1,
            sender=self.profile2,
            notification_type=NotificationType.LIKE_POST,
            title="Read notification",
            message="This notification is read",
            post=self.post,
            is_read=True
        )
        Notification.objects.create(
            recipient=self.profile1,
            sender=self.profile2,
            notification_type=NotificationType.LIKE_POST,
            title="Unread notification",
            message="This notification is unread",
            post=self.post,
            is_read=False
        )
        
        self.authenticate(self.profile1.id)
        url = reverse('notifications_app:get_notification_counts')
        response = self.client.get(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total_count'], 2)
        self.assertEqual(response.data['unread_count'], 1)
    
    def test_mark_all_notifications_read(self):
        """Test marking all notifications as read."""
        # Create unread notifications
        Notification.objects.create(
            recipient=self.profile1,
            sender=self.profile2,
            notification_type=NotificationType.LIKE_POST,
            title="Unread notification 1",
            message="This notification is unread",
            post=self.post,
            is_read=False
        )
        Notification.objects.create(
            recipient=self.profile1,
            sender=self.profile2,
            notification_type=NotificationType.LIKE_POST,
            title="Unread notification 2",
            message="This notification is unread",
            post=self.post,
            is_read=False
        )
        
        self.authenticate(self.profile1.id)
        url = reverse('notifications_app:mark_all_notifications_read')
        response = self.client.post(url)
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['updated_count'], 2)
        
        # Verify all notifications are now read
        unread_count = Notification.objects.filter(
            recipient=self.profile1,
            is_read=False
        ).count()
        self.assertEqual(unread_count, 0)
