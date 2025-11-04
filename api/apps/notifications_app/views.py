from rest_framework import generics, permissions
from rest_framework.response import Response
from rest_framework.decorators import api_view, permission_classes
from django.db.models import Count, Q
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter
from drf_spectacular.types import OpenApiTypes

from .models import Notification
from .serializers import NotificationSerializer, NotificationUpdateSerializer
from .pagination import NotificationsPagination

# Reusable parameter for API documentation
auth_profile_param = OpenApiParameter(
    "auth-profile-id",
    OpenApiTypes.STR,
    location=OpenApiParameter.HEADER,
    description="Profile ID for authentication",
    required=True,
)


class BaseNotificationView(generics.ListAPIView):
    """Base view for notification endpoints with common functionality."""
    
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return base queryset with security filtering."""
        return Notification.objects.filter(
            recipient=self.request.current_profile
        ).select_related('sender', 'post')


@extend_schema_view(get=extend_schema(parameters=[auth_profile_param]))
class ListNotificationsView(BaseNotificationView):
    """List all notifications for the authenticated profile."""
    pagination_class = NotificationsPagination
    
    def list(self, request, *args, **kwargs):
        """Override list to include unread count in response."""
        response = super().list(request, *args, **kwargs)
        
        # Get unread count for the current profile
        unread_count = Notification.objects.filter(
            recipient=request.current_profile,
            is_read=False
        ).count()
        
        # Add unread count to the response data
        if isinstance(response.data, dict):
            response.data['extra_data'] = {'unread_count': unread_count}
        
        return response


@extend_schema_view(get=extend_schema(parameters=[auth_profile_param]))
class ListUnreadNotificationsView(BaseNotificationView):
    """List unread notifications for the authenticated profile."""
    
    def get_queryset(self):
        return super().get_queryset().filter(is_read=False)


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
    patch=extend_schema(parameters=[auth_profile_param])
)
class RetrieveUpdateNotificationView(generics.RetrieveUpdateAPIView):
    """Retrieve and update a specific notification."""
    
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Return notifications for the current profile only."""
        return Notification.objects.filter(recipient=self.request.current_profile)
    
    def get_serializer_class(self):
        return NotificationUpdateSerializer if self.request.method == 'PATCH' else NotificationSerializer


@extend_schema(
    parameters=[auth_profile_param],
    request=None,
    responses={200: {"type": "object", "properties": {"message": {"type": "string"}, "updated_count": {"type": "integer"}}}}
)
@api_view(['POST'])
@permission_classes([permissions.IsAuthenticated])
def mark_all_notifications_read(request):
    """Mark all notifications as read for the authenticated profile."""
    updated_count = Notification.objects.filter(
        recipient=request.current_profile,
        is_read=False
    ).update(is_read=True)
    
    return Response({
        'message': f'Marked {updated_count} notifications as read',
        'updated_count': updated_count
    })


@extend_schema(
    parameters=[auth_profile_param],
    responses={200: {"type": "object", "properties": {"total_count": {"type": "integer"}, "unread_count": {"type": "integer"}}}}
)
@api_view(['GET'])
@permission_classes([permissions.IsAuthenticated])
def get_notification_counts(request):
    """Get notification counts for the authenticated profile."""
    counts = Notification.objects.filter(
        recipient=request.current_profile
    ).aggregate(
        total_count=Count('id'),
        unread_count=Count('id', filter=Q(is_read=False))
    )
    
    return Response(counts)
