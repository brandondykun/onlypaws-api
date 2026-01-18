from rest_framework import generics, permissions
from django.utils import timezone
from django.db.models import Q, Case, When, Value, IntegerField
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiParameter

from core.schema_params import auth_profile_param
from .models import Announcement, AnnouncementPriority
from .serializers import AnnouncementSerializer


@extend_schema_view(
    get=extend_schema(
        parameters=[
            auth_profile_param,
            OpenApiParameter(
                name='exclude_welcome',
                type=str,
                location=OpenApiParameter.QUERY,
                description='Set to "true" to exclude welcome announcements',
                required=False,
            ),
        ]
    )
)
class AnnouncementListView(generics.ListAPIView):
    """
    List active announcements.
    
    Returns announcements that are:
    - Active (is_active=True)
    - Within their display period (start_date <= now <= end_date or end_date is null)
    
    Query Parameters:
    - exclude_welcome: Set to 'true' to filter out announcements with type 'welcome'
    """
    
    serializer_class = AnnouncementSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None
    
    def get_queryset(self):
        now = timezone.now()
        
        queryset = Announcement.objects.filter(
            is_active=True,
            start_date__lte=now
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=now)
        )
        
        # Handle exclude_welcome query parameter
        exclude_welcome = self.request.query_params.get('exclude_welcome', 'false')
        if exclude_welcome.lower() == 'true':
            queryset = queryset.exclude(announcement_type='welcome')
        
        # Order by priority (high > normal > low) then by created_at descending
        # Using Case/When to ensure proper priority ordering
        queryset = queryset.annotate(
            priority_order=Case(
                When(priority=AnnouncementPriority.HIGH, then=Value(0)),
                When(priority=AnnouncementPriority.NORMAL, then=Value(1)),
                When(priority=AnnouncementPriority.LOW, then=Value(2)),
                default=Value(1),
                output_field=IntegerField(),
            )
        ).order_by('priority_order', '-created_at')
        
        return queryset

