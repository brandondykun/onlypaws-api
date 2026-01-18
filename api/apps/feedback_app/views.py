from typing import Any
from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import OrderingFilter, SearchFilter
from django.contrib.auth import get_user_model
from drf_spectacular.utils import extend_schema, extend_schema_view

from .models import Feedback, FeedbackComment
from .serializers import (
    FeedbackSerializer,
    FeedbackCreateSerializer,
    FeedbackUpdateSerializer,
    FeedbackListSerializer,
    FeedbackCommentSerializer,
)
from .permissions import (
    IsStaffOrReadOnlyForReporter,
    IsStaffForComments,
)
from .pagination import FeedbackPagination

User = get_user_model()


@extend_schema_view(
    list=extend_schema(
        summary="List feedback tickets",
        description="Get a list of feedback tickets. Regular users see only their own tickets, staff see all.",
    ),
    create=extend_schema(
        summary="Create feedback ticket",
        description="Create a new feedback ticket. The reporter is automatically set to the current user.",
    ),
    retrieve=extend_schema(
        summary="Get feedback ticket",
        description="Get details of a specific feedback ticket including comments.",
    ),
    update=extend_schema(
        summary="Update feedback ticket",
        description="Update feedback ticket. Only staff can update status, priority, and assignee.",
    ),
    partial_update=extend_schema(
        summary="Partially update feedback ticket",
        description="Partially update feedback ticket. Only staff can update status, priority, and assignee.",
    ),
    destroy=extend_schema(
        summary="Delete feedback ticket",
        description="Delete a feedback ticket. Only staff can delete tickets.",
    ),
)
class FeedbackViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing feedback tickets.

    - Regular users can create feedback and view their own tickets
    - Staff members can view all tickets and update status/priority/assignee
    - Only staff can delete tickets
    """

    queryset = Feedback.objects.all()
    permission_classes = [permissions.IsAuthenticated, IsStaffOrReadOnlyForReporter]
    filter_backends = [SearchFilter, OrderingFilter]
    pagination_class = FeedbackPagination
    search_fields = ["title", "description"]
    ordering_fields = ["created_at", "updated_at", "priority"]
    ordering = ["-created_at"]

    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == "create":
            return FeedbackCreateSerializer
        elif self.action in ["update", "partial_update"]:
            return FeedbackUpdateSerializer
        elif self.action == "list":
            return FeedbackListSerializer
        return FeedbackSerializer

    def get_queryset(self):
        """Filter queryset based on user permissions and query parameters"""
        queryset = super().get_queryset()

        # Apply user permission filtering
        # - 'list' action: all users see only their own tickets
        # - Other actions: staff can access any ticket, non-staff only their own
        if self.action == "list" or not self.request.user.is_staff:
            queryset = queryset.filter(reporter=self.request.user)

        # Apply query parameter filtering
        ticket_type = self.request.query_params.get("ticket_type")
        if ticket_type:
            queryset = queryset.filter(ticket_type=ticket_type)

        status_filter = self.request.query_params.get("status")
        if status_filter:
            queryset = queryset.filter(status=status_filter)

        priority = self.request.query_params.get("priority")
        if priority:
            queryset = queryset.filter(priority=priority)

        assignee = self.request.query_params.get("assignee")
        if assignee:
            try:
                assignee_id = int(assignee)
                queryset = queryset.filter(assignee_id=assignee_id)
            except (ValueError, TypeError):
                # Invalid assignee ID, return empty queryset
                queryset = queryset.none()

        # Optimize database queries with select_related and prefetch_related
        queryset = queryset.select_related("reporter", "assignee")

        # Only prefetch comments for detail views or when needed
        if self.action in ["retrieve", "list"]:
            queryset = queryset.prefetch_related("comments__author")

        return queryset

    def perform_create(self, serializer):
        """Set the reporter to the current user when creating feedback"""
        serializer.save(reporter=self.request.user)

    def update(self, request, *args, **kwargs):
        """Only allow staff to update feedback"""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can update feedback tickets."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Only allow staff to partially update feedback"""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can update feedback tickets."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Only allow staff to delete feedback"""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can delete feedback tickets."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)

    @extend_schema(
        summary="Get my feedback tickets",
        description="Get all feedback tickets created by the current user",
    )
    @action(detail=False, methods=["get"])
    def my_tickets(self, request):
        """Get all feedback tickets for the current user"""
        queryset = self.get_queryset().filter(reporter=request.user)

        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = FeedbackListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = FeedbackListSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        summary="Get assigned tickets",
        description="Get all feedback tickets assigned to the current staff user",
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated, permissions.IsAdminUser],
    )
    def assigned_to_me(self, request):
        """Get all feedback tickets assigned to the current staff user"""
        queryset = self.get_queryset().filter(assignee=request.user)

        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = FeedbackListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = FeedbackListSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)

    @extend_schema(
        summary="List all feedback tickets",
        description="Get all feedback tickets in the system. Only accessible by staff members.",
    )
    @action(
        detail=False,
        methods=["get"],
        permission_classes=[permissions.IsAuthenticated, permissions.IsAdminUser],
    )
    def all_tickets(self, request):
        """Get all feedback tickets (staff only)"""
        queryset = self.get_queryset()

        # Apply pagination
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = FeedbackListSerializer(
                page, many=True, context={"request": request}
            )
            return self.get_paginated_response(serializer.data)

        serializer = FeedbackListSerializer(
            queryset, many=True, context={"request": request}
        )
        return Response(serializer.data)


@extend_schema_view(
    list=extend_schema(
        summary="List feedback comments",
        description="Get comments for a specific feedback ticket",
    ),
    create=extend_schema(
        summary="Create feedback comment",
        description="Add a comment to a feedback ticket. Only staff can create comments.",
    ),
    retrieve=extend_schema(
        summary="Get feedback comment", description="Get details of a specific comment"
    ),
    update=extend_schema(
        summary="Update feedback comment",
        description="Update a comment. Only staff can update comments.",
    ),
    partial_update=extend_schema(
        summary="Partially update feedback comment",
        description="Partially update a comment. Only staff can update comments.",
    ),
    destroy=extend_schema(
        summary="Delete feedback comment",
        description="Delete a comment. Only staff can delete comments.",
    ),
)
class FeedbackCommentViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing feedback comments.

    - Only staff members can create, update, and delete comments
    - Users can read comments on their own feedback tickets
    - Internal comments are only visible to staff
    """

    serializer_class = FeedbackCommentSerializer
    permission_classes = [permissions.IsAuthenticated, IsStaffForComments]
    filter_backends = [OrderingFilter]
    ordering = ["created_at"]
    # Provide base queryset for schema introspection
    queryset = FeedbackComment.objects.all()

    def get_queryset(self):
        """Filter queryset based on user permissions, ticket access, and query parameters"""
        queryset = FeedbackComment.objects.select_related(
            "author", "ticket", "ticket__reporter"
        )

        # Apply user permission filtering
        if not self.request.user.is_staff:
            # Regular users can only see non-internal comments on their own tickets
            queryset = queryset.filter(
                ticket__reporter=self.request.user, is_internal=False
            )

        # Apply query parameter filtering
        ticket_id = self.request.query_params.get("ticket")
        if ticket_id:
            try:
                ticket_id = int(ticket_id)
                queryset = queryset.filter(ticket_id=ticket_id)
            except (ValueError, TypeError):
                # Invalid ticket ID, return empty queryset
                queryset = queryset.none()

        is_internal = self.request.query_params.get("is_internal")
        if is_internal is not None and self.request.user.is_staff:
            # Only staff can filter by is_internal
            queryset = queryset.filter(is_internal=is_internal.lower() == "true")

        return queryset

    def perform_create(self, serializer):
        """Set the author to the current user when creating a comment"""
        serializer.save(author=self.request.user)

    def create(self, request, *args, **kwargs):
        """Only allow staff to create comments"""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can create comments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().create(request, *args, **kwargs)

    def update(self, request, *args, **kwargs):
        """Only allow staff to update comments"""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can update comments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().update(request, *args, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        """Only allow staff to partially update comments"""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can update comments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        """Only allow staff to delete comments"""
        if not request.user.is_staff:
            return Response(
                {"detail": "Only staff members can delete comments."},
                status=status.HTTP_403_FORBIDDEN,
            )
        return super().destroy(request, *args, **kwargs)
