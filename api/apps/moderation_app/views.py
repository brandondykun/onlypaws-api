"""
Views for the moderation app.
"""
from rest_framework import permissions, mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework import status
from apps.moderation_app.models import ReportReason, PostReport
from .serializers import (
    ReportReasonSerializer,
    CreatePostReportSerializer,
    PostReportDetailSerializer,
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


@extend_schema_view(
    list=extend_schema(parameters=[auth_profile_param]),
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
        requesting_profile = self.request.current_profile
        if self.request.user.is_staff:
            return PostReport.objects.all().order_by("created_at")
        return PostReport.objects.filter(reporter=requesting_profile).order_by(
            "-created_at"
        )

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
                    f"Post report created by profile {request.current_profile.id}: "
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

    @extend_schema(parameters=[auth_profile_param])
    @action(detail=False, methods=["get"])
    def my_reports(self, request):
        """
        Endpoint for users to view their own reports
        """
        requesting_profile = request.current_profile

        queryset = PostReport.objects.filter(reporter=requesting_profile)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = PostReportDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # If pagination is disabled, serialize and return all results
        serializer = PostReportDetailSerializer(queryset, many=True)
        return Response(serializer.data)

    @extend_schema(parameters=[auth_profile_param])
    @action(detail=False, methods=["get"])
    def reported_posts(self, request):
        """
        Endpoint for users to view reports on their posts
        """
        requesting_profile = request.current_profile

        queryset = PostReport.objects.filter(post__profile=requesting_profile)
        page = self.paginate_queryset(queryset)

        if page is not None:
            serializer = PostReportDetailSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)

        # If pagination is disabled, serialize and return all results
        serializer = PostReportDetailSerializer(queryset, many=True)
        return Response(serializer.data)
