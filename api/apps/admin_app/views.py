"""
Views for the admin dashboard app.

All views in this app require admin (staff) permissions.
"""

from rest_framework import permissions, status, generics, filters
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, OpenApiParameter

from apps.profile_app.models import Profile
from apps.feedback_app.models import Feedback
from apps.moderation_app.models import PostReport, ReportReason
from apps.announcements_app.models import Announcement
from .serializers import (
    AdminUserSerializer,
    AdminUserDetailSerializer,
    AdminProfileSerializer,
    AdminProfileDetailSerializer,
    AdminAnnouncementSerializer,
    AdminAnnouncementDetailSerializer,
    AdminReportReasonSerializer,
    AdminReportReasonDetailSerializer,
)
from .pagination import AdminPagination

User = get_user_model()


class AdminDashboardStatsView(APIView):
    """
    API endpoint for fetching admin dashboard statistics.

    Returns aggregate data for the admin dashboard including:
    - Total active users count
    - Total profiles count
    - Open feedback tickets count
    - Pending post reports count
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]

    @extend_schema(
        summary="Get admin dashboard statistics",
        description="Fetch aggregate statistics for the admin dashboard. Admin only.",
        responses={
            200: {
                "type": "object",
                "properties": {
                    "active_users_count": {
                        "type": "integer",
                        "description": "Total number of active users",
                    },
                    "total_profiles_count": {
                        "type": "integer",
                        "description": "Total number of profiles",
                    },
                    "open_feedback_count": {
                        "type": "integer",
                        "description": "Number of feedback tickets with OPEN status",
                    },
                    "pending_reports_count": {
                        "type": "integer",
                        "description": "Number of post reports with PENDING status",
                    },
                },
            },
        },
    )
    def get(self, request):
        """Return dashboard statistics."""
        active_users_count = User.objects.filter(is_active=True).count()
        total_profiles_count = Profile.objects.count()
        open_feedback_count = Feedback.objects.filter(
            status=Feedback.FeedbackStatus.OPEN
        ).count()
        pending_reports_count = PostReport.objects.filter(
            status=PostReport.ReportStatus.PENDING
        ).count()

        return Response(
            {
                "active_users_count": active_users_count,
                "total_profiles_count": total_profiles_count,
                "open_feedback_count": open_feedback_count,
                "pending_reports_count": pending_reports_count,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema(
    summary="List all users",
    description="Fetch a paginated list of all users. Supports search by email. Admin only.",
    parameters=[
        OpenApiParameter(
            name="search",
            description="Search users by email",
            required=False,
            type=str,
        ),
    ],
)
class AdminUserListView(generics.ListAPIView):
    """
    API endpoint for listing all users.

    Supports:
    - Pagination
    - Search by email
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = AdminUserSerializer
    pagination_class = AdminPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["email"]
    ordering_fields = ["id", "email", "is_active"]
    ordering = ["id"]

    def get_queryset(self):
        return User.objects.all().prefetch_related("profiles")


@extend_schema(
    summary="Get user details",
    description="Fetch detailed information for a specific user by ID. Admin only.",
)
class AdminUserDetailView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving a single user's details.

    Returns all user fields except password, plus their profiles.
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = AdminUserDetailSerializer

    def get_queryset(self):
        return User.objects.all().prefetch_related("profiles", "profiles__image")


@extend_schema(
    summary="List all profiles",
    description="Fetch a paginated list of all profiles. Supports search by username. Admin only.",
    parameters=[
        OpenApiParameter(
            name="search",
            description="Search profiles by username",
            required=False,
            type=str,
        ),
    ],
)
class AdminProfileListView(generics.ListAPIView):
    """
    API endpoint for listing all profiles.

    Supports:
    - Pagination
    - Search by username
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = AdminProfileSerializer
    pagination_class = AdminPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["username"]
    ordering_fields = ["id", "username", "created_at", "is_active"]
    ordering = ["id"]

    def get_queryset(self):
        return Profile.objects.all().select_related("user", "image")


@extend_schema(
    summary="Get profile details",
    description="Fetch detailed information for a specific profile including user info. Admin only.",
)
class AdminProfileDetailView(generics.RetrieveAPIView):
    """
    API endpoint for retrieving a single profile's details.

    Returns detailed profile information including:
    - User ID and email
    - Profile stats (posts, followers, following counts)
    - Profile type-specific fields
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = AdminProfileDetailSerializer

    def get_queryset(self):
        return Profile.objects.all().select_related(
            "user", "image", "regularprofile", "businessprofile"
        )


@extend_schema(
    summary="List all announcements",
    description="Fetch a paginated list of all announcements. Supports search by title. Admin only.",
    parameters=[
        OpenApiParameter(
            name="search",
            description="Search announcements by title",
            required=False,
            type=str,
        ),
    ],
)
class AdminAnnouncementListView(generics.ListAPIView):
    """
    API endpoint for listing all announcements.

    Supports:
    - Pagination
    - Search by title
    - Ordering by priority, created_at, start_date
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = AdminAnnouncementSerializer
    pagination_class = AdminPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["title"]
    ordering_fields = ["id", "priority", "created_at", "start_date", "is_active"]
    ordering = ["-priority", "-created_at"]

    def get_queryset(self):
        return Announcement.objects.all()


@extend_schema(
    summary="Get, update, or delete an announcement",
    description="Fetch, update, or delete a specific announcement by ID. Admin only.",
)
class AdminAnnouncementDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single announcement.

    Supports:
    - GET: Retrieve announcement details
    - PUT/PATCH: Update announcement fields
    - DELETE: Remove announcement
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = AdminAnnouncementDetailSerializer

    def get_queryset(self):
        return Announcement.objects.all()


@extend_schema(
    summary="List all report reasons",
    description="Fetch a paginated list of all report reasons. Supports search by name. Admin only.",
    parameters=[
        OpenApiParameter(
            name="search",
            description="Search report reasons by name",
            required=False,
            type=str,
        ),
    ],
)
class AdminReportReasonListView(generics.ListAPIView):
    """
    API endpoint for listing all report reasons.

    Supports:
    - Pagination
    - Search by name
    - Ordering by id, name, is_active, created_at
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = AdminReportReasonSerializer
    pagination_class = AdminPagination
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ["name"]
    ordering_fields = ["id", "name", "is_active", "created_at"]
    ordering = ["name"]

    def get_queryset(self):
        return ReportReason.objects.all()


@extend_schema(
    summary="Get, update, or delete a report reason",
    description="Fetch, update, or delete a specific report reason by ID. Admin only.",
)
class AdminReportReasonDetailView(generics.RetrieveUpdateDestroyAPIView):
    """
    API endpoint for retrieving, updating, or deleting a single report reason.

    Supports:
    - GET: Retrieve report reason details
    - PUT/PATCH: Update report reason fields
    - DELETE: Remove report reason
    """

    permission_classes = [permissions.IsAuthenticated, permissions.IsAdminUser]
    serializer_class = AdminReportReasonDetailSerializer

    def get_queryset(self):
        return ReportReason.objects.all()

