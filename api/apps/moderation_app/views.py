"""
Views for the moderation app.
"""
from rest_framework import permissions, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from rest_framework.views import APIView
from apps.moderation_app.models import ReportReason, PostReport, ProfileReportReason, ProfileReport
from apps.core_app.profanity_service import check_and_log_text
from .serializers import (
    ReportReasonSerializer,
    CreatePostReportSerializer,
    PostReportDetailSerializer,
    ProfileReportReasonSerializer,
    CreateProfileReportSerializer,
    ProfileReportDetailSerializer,
)
from .pagination import ReportPostsPagination
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
)
import logging

from core.schema_params import auth_profile_param

logger = logging.getLogger(__name__)


@extend_schema_view(
    list=extend_schema(parameters=[auth_profile_param]),
    retrieve=extend_schema(parameters=[auth_profile_param]),
)
class ReportReasonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing active report reasons.
    Only GET methods are allowed as reasons should be managed via admin.
    """

    queryset = ReportReason.objects.filter(is_active=True)
    serializer_class = ReportReasonSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        if not request.current_profile:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


status_filter_param = OpenApiParameter(
    name="status",
    description="Filter reports by status (PENDING, UNDER_REVIEW, RESOLVED, DISMISSED)",
    required=False,
    type=str,
    location=OpenApiParameter.QUERY,
)


@extend_schema_view(
    list=extend_schema(parameters=[auth_profile_param, status_filter_param]),
    retrieve=extend_schema(
        parameters=[
            auth_profile_param,
            OpenApiParameter(
                name="id",
                description="Report ID",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            ),
        ]
    ),
    create=extend_schema(parameters=[auth_profile_param]),
)
class PostReportViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for managing post reports.
    Users can create reports and view their own reports.
    Staff can view and manage all reports.
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ReportPostsPagination
    # Provide base queryset for schema introspection
    queryset = PostReport.objects.all()

    def get_queryset(self):
        if self.request.user.is_staff:
            queryset = PostReport.objects.all().order_by("created_at")
        else:
            queryset = PostReport.objects.filter(reporter=self.request.user).order_by(
                "-created_at"
            )
        queryset = queryset.select_related("post__profile", "reason", "reporter")
        return self._apply_status_filter(queryset)

    def _apply_status_filter(self, queryset):
        """Apply status filter if provided in query params."""
        status_param = self.request.query_params.get("status")
        if status_param:
            # Normalize to uppercase for case-insensitive matching
            status_param = status_param.upper()
            if status_param in dict(PostReport.ReportStatus.choices):
                queryset = queryset.filter(status=status_param)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreatePostReportSerializer
        return PostReportDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        """Override create to add logging for report creation."""
        try:
            response = super().create(request, *args, **kwargs)
            if response.status_code == 201:
                logger.info(
                    f"Post report created by user {request.user.id}: "
                    f"post {request.data.get('post')}, reason {request.data.get('reason')}"
                )
            return response
        except Exception as e:
            logger.error(
                f"Error creating post report: {str(e)}",
                exc_info=True
            )
            return Response(
                {"error": "Failed to create report"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(parameters=[auth_profile_param])
    @action(
        detail=True, methods=["patch"], permission_classes=[permissions.IsAdminUser]
    )
    def resolve(self, request, pk=None):
        """
        Endpoint for staff to resolve a report
        """
        resolving_profile = request.current_profile

        report = self.get_object()
        resolution_note = request.data.get("resolution_note", "")
        request_status = request.data.get("status", PostReport.ReportStatus.RESOLVED)

        if request_status not in dict(PostReport.ReportStatus.choices):
            logger.warning(
                f"Invalid status '{request_status}' provided for report {pk} "
                f"by profile {resolving_profile.id}"
            )
            return Response(
                {"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST
            )

        old_status = report.status
        report.status = request_status
        report.resolution_note = resolution_note
        report.resolved_by = resolving_profile
        report.save()

        logger.info(
            f"Report {pk} resolved: status changed from {old_status} to {request_status} "
            f"by profile {resolving_profile.id}"
        )

        return Response(PostReportDetailSerializer(report).data)

    @extend_schema(parameters=[auth_profile_param, status_filter_param])
    @action(detail=False, methods=["get"])
    def my_reports(self, request):
        """
        Endpoint for users to view their own reports
        """
        queryset = PostReport.objects.filter(reporter=request.user)
        queryset = self._apply_status_filter(queryset)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = PostReportDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # If pagination is disabled, serialize and return all results
        serializer = PostReportDetailSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(parameters=[auth_profile_param, status_filter_param])
    @action(detail=False, methods=["get"])
    def reported_posts(self, request):
        """
        Endpoint for users to view reports on their posts
        """
        requesting_profile = request.current_profile

        queryset = PostReport.objects.filter(post__profile=requesting_profile)
        queryset = self._apply_status_filter(queryset)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = PostReportDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # If pagination is disabled, serialize and return all results
        serializer = PostReportDetailSerializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(parameters=[auth_profile_param]),
    retrieve=extend_schema(parameters=[auth_profile_param]),
)
class ProfileReportReasonViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for listing active profile report reasons.
    Only GET methods are allowed as reasons should be managed via admin.
    """

    queryset = ProfileReportReason.objects.filter(is_active=True)
    serializer_class = ProfileReportReasonSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = None

    def list(self, request, *args, **kwargs):
        if not request.current_profile:
            return Response(status=status.HTTP_401_UNAUTHORIZED)
        queryset = self.filter_queryset(self.get_queryset())

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(parameters=[auth_profile_param, status_filter_param]),
    retrieve=extend_schema(
        parameters=[
            auth_profile_param,
            OpenApiParameter(
                name="id",
                description="Profile Report ID",
                required=True,
                type=int,
                location=OpenApiParameter.PATH,
            ),
        ]
    ),
    create=extend_schema(parameters=[auth_profile_param]),
)
class ProfileReportViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    ViewSet for managing profile reports.
    Users can create reports and view their own reports.
    Staff can view and manage all reports.
    """

    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ReportPostsPagination
    queryset = ProfileReport.objects.all()

    def get_queryset(self):
        if self.request.user.is_staff:
            queryset = ProfileReport.objects.all().order_by("created_at")
        else:
            queryset = ProfileReport.objects.filter(reporter=self.request.user).order_by(
                "-created_at"
            )
        return self._apply_status_filter(queryset)

    def _apply_status_filter(self, queryset):
        """Apply status filter if provided in query params."""
        status_param = self.request.query_params.get("status")
        if status_param:
            status_param = status_param.upper()
            if status_param in dict(ProfileReport.ReportStatus.choices):
                queryset = queryset.filter(status=status_param)
        return queryset

    def get_serializer_class(self):
        if self.action == "create":
            return CreateProfileReportSerializer
        return ProfileReportDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    def create(self, request, *args, **kwargs):
        """Override create to add logging for report creation."""
        try:
            response = super().create(request, *args, **kwargs)
            if response.status_code == 201:
                logger.info(
                    f"Profile report created by user {request.user.id}: "
                    f"profile {request.data.get('profile')}, reason {request.data.get('reason')}"
                )
            return response
        except Exception as e:
            logger.error(
                f"Error creating profile report: {str(e)}",
                exc_info=True
            )
            return Response(
                {"error": "Failed to create report"},
                status=status.HTTP_400_BAD_REQUEST
            )

    @extend_schema(parameters=[auth_profile_param])
    @action(
        detail=True, methods=["patch"], permission_classes=[permissions.IsAdminUser]
    )
    def resolve(self, request, pk=None):
        """
        Endpoint for staff to resolve a profile report
        """
        resolving_profile = request.current_profile

        report = self.get_object()
        resolution_note = request.data.get("resolution_note", "")
        request_status = request.data.get("status", ProfileReport.ReportStatus.RESOLVED)

        if request_status not in dict(ProfileReport.ReportStatus.choices):
            logger.warning(
                f"Invalid status '{request_status}' provided for profile report {pk} "
                f"by profile {resolving_profile.id}"
            )
            return Response(
                {"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST
            )

        old_status = report.status
        report.status = request_status
        report.resolution_note = resolution_note
        report.resolved_by = resolving_profile
        report.save()

        logger.info(
            f"Profile report {pk} resolved: status changed from {old_status} to {request_status} "
            f"by profile {resolving_profile.id}"
        )

        return Response(ProfileReportDetailSerializer(report).data)


class CheckTextView(APIView):
    """Check if text contains profanity. Used before uploads to avoid wasted bandwidth."""
    permission_classes = [permissions.IsAuthenticated]

    @extend_schema(
        request={"application/json": {"type": "object", "properties": {"text": {"type": "string"}}}},
        responses={200: {"type": "object", "properties": {"allowed": {"type": "boolean"}, "message": {"type": "string"}}}},
    )
    def post(self, request):
        text = request.data.get("text", "")
        if not text:
            return Response({"allowed": True})

        profile = getattr(request, "current_profile", None)
        profile_id = profile.id if profile else None
        is_profane = check_and_log_text(text, "PRE_UPLOAD_CHECK", profile_id=profile_id)
        if is_profane:
            return Response({
                "allowed": False,
                "message": "That text contains inappropriate language."
            })
        return Response({"allowed": True})
