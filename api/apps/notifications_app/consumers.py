import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth.models import AnonymousUser
from rest_framework_simplejwt.tokens import AccessToken
from rest_framework_simplejwt.exceptions import InvalidToken, TokenError
from apps.user_app.models import User
from apps.profile_app.models import Profile

logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time notifications."""
    
    async def connect(self):
        """Handle WebSocket connection."""
        try:
            # Extract profile_public_id from URL route (ULID string)
            self.profile_public_id = self.scope['url_route']['kwargs']['profile_public_id']

            # Authenticate the user
            user = await self.get_user_from_token()
            if not user or user == AnonymousUser():
                logger.warning(f"Authentication failed for WebSocket connection to profile {self.profile_public_id}")
                await self.close(code=4001)
                return

            # Resolve profile by public_id and verify the user owns it
            profile = await self.get_profile_by_public_id(user, self.profile_public_id)
            if not profile:
                logger.warning(f"Profile {self.profile_public_id} not found or not owned by user {user.id}")
                await self.close(code=4003)
                return

            self.user = user
            self.profile = profile
            # Channel layer group is keyed by profile.id so existing senders unchanged
            self.profile_group_name = f'profile_{self.profile.id}'

            # Join profile group
            await self.channel_layer.group_add(
                self.profile_group_name,
                self.channel_name
            )
            
            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': f'Connected to notifications for profile {profile.username}'
            }))
            
            logger.info(f"WebSocket connected for profile {profile.username}")
            
        except KeyError as e:
            logger.error(f"Missing required parameter in WebSocket connection: {e}")
            await self.close(code=4000)
        except Exception as e:
            logger.error(f"Unexpected error in WebSocket connect: {e}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        if hasattr(self, 'profile_group_name'):
            await self.channel_layer.group_discard(
                self.profile_group_name,
                self.channel_name
            )
            
        if hasattr(self, 'profile'):
            logger.info(f"WebSocket disconnected for profile {self.profile.username}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        # Rate limiting: ignore if too much data
        if len(text_data) > 1024:  # 1KB limit
            logger.warning(f"Message too large from profile {getattr(self, 'profile', 'unknown')}")
            return
            
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'ping':
                await self.send(text_data=json.dumps({
                    'type': 'pong',
                    'timestamp': data.get('timestamp')
                }))
            elif message_type == 'mark_notification_read':
                notification_id = data.get('notification_id')
                if isinstance(notification_id, int) and notification_id > 0:
                    success = await self.mark_notification_read(notification_id)
                    await self.send(text_data=json.dumps({
                        'type': 'notification_read_status',
                        'notification_id': notification_id,
                        'success': success
                    }))
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except json.JSONDecodeError:
            logger.warning("Invalid JSON received in WebSocket")
        except Exception as e:
            logger.error(f"Error processing WebSocket message: {e}")

    async def notification_message(self, event):
        """Handle notification messages sent to the group."""
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': event['notification']
        }))

    async def system_message(self, event):
        """Handle system messages sent to the group."""
        await self.send(text_data=json.dumps({
            'type': 'system_message',
            'message': event['message'],
            'data': event.get('data', {})
        }))

    async def post_ready(self, event):
        """Handle post ready messages sent to the group."""
        await self.send(text_data=json.dumps({
            'type': 'post_ready',
            'post_id': event['post_id'],
            'post_public_id': event.get('post_public_id'),
            'message': event.get('message', 'Your post is ready'),
        }))

    @database_sync_to_async
    def get_user_from_token(self):
        """Extract and validate user from JWT token."""
        try:
            query_string = self.scope.get('query_string', b'').decode()
            
            # Extract token more securely
            token = None
            for param in query_string.split('&'):
                if param.startswith('token='):
                    token = param.split('=', 1)[1]
                    # Basic URL decode (handles %20, etc.)
                    token = token.replace('%20', ' ').replace('%3D', '=')
                    break
            
            if not token:
                logger.warning("No token provided in WebSocket connection")
                return AnonymousUser()
            
            # Validate token and get user
            access_token = AccessToken(token)
            user_id = access_token.get('user_id')
            if not user_id:
                logger.warning("No user_id in JWT token")
                return AnonymousUser()
                
            return User.objects.select_related().get(id=user_id)
            
        except (InvalidToken, TokenError) as e:
            logger.warning(f"Invalid JWT token in WebSocket connection: {e}")
            return AnonymousUser()
        except User.DoesNotExist:
            logger.warning("User not found for JWT token")
            return AnonymousUser()
        except Exception as e:
            logger.error(f"Unexpected error in token validation: {e}")
            return AnonymousUser()

    @database_sync_to_async
    def get_profile_by_public_id(self, user, profile_public_id):
        """Get profile by public_id (ULID) and verify the user owns it."""
        try:
            return user.profiles.get(public_id=profile_public_id)
        except Profile.DoesNotExist as e:
            logger.error(f"Profile {profile_public_id} not found or not owned by user {user.id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting profile {profile_public_id} for user {user.id}: {e}")
            return None

    @database_sync_to_async
    def mark_notification_read(self, notification_id):
        """Mark a notification as read with proper security checks."""
        try:
            from .models import Notification
            # Use update() for better performance and security
            updated = Notification.objects.filter(
                id=notification_id,
                recipient=self.profile,
                is_read=False  # Only update if not already read
            ).update(is_read=True)
            return updated > 0
        except Exception as e:
            logger.error(f"Error marking notification {notification_id} as read: {e}")
            return False
