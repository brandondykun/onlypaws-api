"""
Views for the posts api.
"""

from rest_framework import generics, permissions, mixins, status, viewsets
from rest_framework.decorators import action
from apps.core_app.models import (
    Post,
    PostImage,
    Profile,
    Like,
    Comment,
    Follow,
    CommentLike,
    SavedPost,
    ReportReason,
    PostReport,
)
from .serializers import (
    PostSerializer,
    LikeSerializer,
    CommentSerializer,
    ProfileDetailsSerializer,
    PostDetailedSerializer,
    CommentDetailedSerializer,
    SearchProfileSerializer,
    FollowSerializer,
    CommentLikeSerializer,
    CreateSavedPostSerializer,
    PostReportDetailSerializer,
    CreatePostReportSerializer,
    ReportReasonSerializer,
)
from ..user_app.serializers import ProfileSerializer
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import transaction
from .pagination import (
    SearchedProfilesPagination,
    ListExplorePostsPagination,
    ListProfilePostsPagination,
    ListSimilarPostsPagination,
    FollowListPagination,
    PostCommentsPagination,
    CommentRepliesPagination,
    ReportReasonPagination,
)
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
)

# schema parameter for auth profile id header
auth_profile_param = OpenApiParameter(
    name="auth-profile-id",
    description="Auth profile id",
    required=True,
    type=str,
    location=OpenApiParameter.HEADER,
)

# schema query param to search for username by text
username_param = OpenApiParameter(
    "username",
    OpenApiTypes.STR,
    description="Username string or substring to search.",
)


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreatePostView(generics.CreateAPIView):
    """Create a new Post."""

    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        profile_id = request.data.get("profileId", None)
        caption = request.data.get("caption", None)
        images = request.FILES.getlist("images")

        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile
        if str(profile_id) != str(current_profile.id) or not caption:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # create post
                data = {
                    "caption": caption,
                    "profile": current_profile.id,
                }
                serializer = self.serializer_class(data=data)
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)

                new_post = Post.objects.get(id=serializer.data["id"])

                for image in images:
                    PostImage.objects.create(image=image, post=new_post)
                new_post = Post.objects.get(id=serializer.data["id"])
                serializer = PostDetailedSerializer(
                    new_post, context={"request": request}
                )
                headers = self.get_success_headers(serializer.data)
                return Response(
                    serializer.data, status=status.HTTP_201_CREATED, headers=headers
                )
        except Exception as e:
            # If an exception occurs, the transaction will be rolled back
            # and the main object will be deleted.
            Response(
                {"message": "Error creating that post."},
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreateLikeView(generics.CreateAPIView):
    """Create or delete a Like."""

    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Like.objects.all()

    def create(self, request, *args, **kwargs):
        post_id = self.kwargs.get("post_id", None)
        profile_id = request.data["profileId"]
        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile
        if str(profile_id) != str(current_profile.id):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # prevent profile from liking own post
        post = get_object_or_404(Post, pk=post_id)
        if post.profile.id == current_profile.id:
            return Response(status=status.HTTP_403_FORBIDDEN)

        new_like_data = {
            "post": post_id,
            "profile": current_profile.id,
        }
        serializer = self.get_serializer(data=new_like_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class DestroyLikeView(generics.DestroyAPIView):
    """Delete a Like."""

    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Like.objects.all()

    def destroy(self, request, *args, **kwargs):
        post_id = self.kwargs.get("pk", None)
        # TODO: don't need this anymore - need to remove from test
        profile_id = self.kwargs.get("profile_id", None)

        current_profile = request.current_profile
        if str(profile_id) != str(current_profile.id):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if post_id:
            like = get_object_or_404(Like, profile=current_profile, post=post_id)
            self.perform_destroy(like)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class ListProfilePostsView(generics.ListAPIView):
    """List all posts from a profile."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ListProfilePostsPagination

    def get_queryset(self):
        profile_id = self.kwargs.get("id", None)
        current_profile = self.request.current_profile

        profile_posts = Post.objects.filter(Q(profile__id=profile_id))

        if str(profile_id) == str(current_profile.id):
            # Don't filter inappropriate posts if profile is requesting their own posts
            return profile_posts.order_by("-created_at")

        # filter reported inappropriate content
        return profile_posts.filter(~Q(reports__reason__id=1)).order_by("-created_at")


class RetrieveProfileView(generics.RetrieveAPIView):
    """Get details of a Profile."""

    serializer_class = ProfileDetailsSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class RetrieveFeedView(generics.ListAPIView):
    """List feed posts from profiles that the authenticated profile follows."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()

    def get(self, request, *args, **kwargs):
        profile_id = self.kwargs.get("id", None)
        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile
        if str(profile_id) != str(current_profile.id):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        requesting_profile_id = self.kwargs.get("id", None)
        posts = Post.objects.filter(
            Q(profile__following__followed_by=requesting_profile_id)
            & ~Q(reports__reason__id=1)  # filter reported inappropriate content
        ).order_by("-created_at")
        return posts


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreateCommentView(generics.CreateAPIView):
    """Create a Comment."""

    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()

    def create(self, request, *args, **kwargs):
        post_id = self.kwargs.get("id")
        text = request.data["text"]
        profile_id = request.data["profileId"]
        parent_comment = request.data["parent_comment"]
        reply_to_comment = request.data["reply_to_comment"]

        # TODO: make sure reply_to_comment is a child comment at some level of parent_comment

        current_profile = request.current_profile

        # ensure that the profile id sent belongs to the current authenticated user profile
        if str(profile_id) != str(current_profile.id):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(
            data={
                "text": text,
                "post": post_id,
                "profile": profile_id,
                "parent_comment": parent_comment,
                "reply_to_comment": reply_to_comment,
            },
            context={"request": request},
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        comment = Comment.objects.get(id=serializer.data["id"])

        res_serializer = CommentDetailedSerializer(
            comment, context={"request": request}
        )
        headers = self.get_success_headers(res_serializer.data)
        return Response(
            res_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class ListPostCommentsView(generics.ListAPIView):
    """List Comments for a Post."""

    serializer_class = CommentDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()
    pagination_class = PostCommentsPagination

    def get_queryset(self):
        post_id = self.kwargs.get("pk")
        comments = self.queryset.filter(
            Q(post=post_id) & Q(parent_comment=None)
        ).order_by("-created_at")
        return comments


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class RetrieveDestroyPostView(generics.RetrieveDestroyAPIView):
    """Get details of a Post."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()

    def get(self, request, *args, **kwargs):
        post_id = self.kwargs.get("pk")
        post = self.queryset.get(id=post_id)
        serializer = self.serializer_class(post, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        # auth_profile_id = request.headers["auth-profile-id"]
        current_profile = request.current_profile
        instance = self.get_object()

        # check that the user requesting the delete owns the post
        if instance.profile.user != self.request.user:
            return Response(
                {"error": "Requesting user does not own this resource."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # check that the profile requesting the delete owns the post
        if instance.profile.id != int(current_profile.id):
            return Response(
                {"error": "Requesting profile does not own this resource."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(get=extend_schema(parameters=[username_param]))
class ListSearchedProfilesView(generics.ListAPIView):
    """List Profiles based on search text."""

    serializer_class = SearchProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()
    pagination_class = SearchedProfilesPagination

    def get(self, request, *args, **kwargs):
        username = self.request.query_params.get("username", None)

        if not username:
            return Response(
                {
                    "message": "Must include username (for searched profile) query param."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        username = self.request.query_params.get("username", None)
        profile_id = self.kwargs.get("id", None)
        profiles = Profile.objects.filter(
            Q(username__icontains=username) & ~Q(id=profile_id)
        ).order_by("username")
        return profiles

    def get_serializer_context(self):
        profile_id = self.kwargs.get("id", None)

        return {
            "profile_id": profile_id,
            "request": self.request,
        }


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreateFollowView(generics.CreateAPIView):
    """Create a follow."""

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    def create(self, request, *args, **kwargs):
        auth_profile_id = self.kwargs.get("id")

        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile
        if str(current_profile.id) != str(auth_profile_id):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        profile_to_follow = get_object_or_404(Profile, pk=request.data["profileId"])
        # profile cannot follow itself
        if profile_to_follow.id == current_profile.id:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        new_follow_data = {
            "followed": request.data["profileId"],
            "followed_by": current_profile.id,
        }
        serializer = self.get_serializer(data=new_follow_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


@extend_schema_view(get=extend_schema(parameters=[username_param]))
class ListFollowersView(generics.ListAPIView):
    """List Profiles that follow a given Profile."""

    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()
    pagination_class = FollowListPagination

    def get_queryset(self):
        profile_id = self.kwargs.get("id", None)
        username = self.request.query_params.get("username", None)

        profile = Profile.objects.get(id=profile_id)
        followers_objs = profile.following.all()
        if username:
            followers_objs = followers_objs.filter(
                Q(followed_by__username__icontains=username)
            )
        sorted = followers_objs.order_by("followed_by__username")
        followers = [obj.followed_by for obj in sorted]
        return followers


@extend_schema_view(get=extend_schema(parameters=[username_param]))
class ListFollowingView(generics.ListAPIView):
    """List Profiles that a given Profile follows."""

    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()
    pagination_class = FollowListPagination

    def get_queryset(self):
        profile_id = self.kwargs.get("id", None)
        username = self.request.query_params.get("username", None)

        profile = Profile.objects.get(id=profile_id)
        following_objs = profile.followers.all()
        if username:
            following_objs = following_objs.filter(
                Q(followed__username__icontains=username)
            )
        sorted = following_objs.order_by("followed__username")
        following = [obj.followed for obj in sorted]
        return following


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class DestroyFollowView(generics.DestroyAPIView):
    """Delete a follow."""

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    def destroy(self, request, *args, **kwargs):
        profile_id = self.kwargs.get("pk")  # profile id to unfollow
        auth_profile_id = self.kwargs.get("auth_profile_id")

        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile
        if str(auth_profile_id) != str(current_profile.id):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if profile_id:
            follow = get_object_or_404(
                Follow, followed_by=auth_profile_id, followed=profile_id
            )
            self.perform_destroy(follow)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class ListExplorePostsView(generics.ListAPIView):
    """List explore posts from profiles that the authenticated profile does not follow."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()
    pagination_class = ListExplorePostsPagination

    def get_queryset(self):
        requesting_profile_id = self.kwargs.get("id")

        posts = Post.objects.filter(
            ~Q(profile__following__followed_by=requesting_profile_id)
            & ~Q(profile__user=self.request.user)
            & ~Q(reports__gt=0)  # filter all reported posts for explore screen
        ).order_by("-created_at")
        return posts


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                "profileId",
                OpenApiTypes.STR,
                description="Requesting profile id.",
            ),
        ]
    )
)
class ListSimilarPostsView(generics.ListAPIView):
    """Get explore posts that are similar to the desired post."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()
    pagination_class = ListSimilarPostsPagination

    def get_queryset(self):
        post_id = self.kwargs.get("pk")
        profile_id = self.request.GET.get("profileId")
        posts = Post.objects.filter(
            ~Q(profile=profile_id)
            & Q(id__gt=post_id)
            & ~Q(reports__reason__id=1)  # filter reported inappropriate content
        ).order_by("-created_at")
        return posts


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreateCommentLikeView(generics.CreateAPIView):
    """Create or delete a Comment Like."""

    serializer_class = CommentLikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CommentLike.objects.all()

    def create(self, request, *args, **kwargs):
        comment_id = self.kwargs.get("comment_id", None)
        profile_id = request.data["profileId"]

        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile

        if str(profile_id) != str(current_profile.id):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        new_like_data = {
            "comment": comment_id,
            "profile": current_profile.id,
        }
        serializer = self.get_serializer(
            data=new_like_data, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class DestroyCommentLikeView(generics.DestroyAPIView):
    """Delete a Comment Like."""

    serializer_class = CommentLikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CommentLike.objects.all()

    def destroy(self, request, *args, **kwargs):
        comment_id = self.kwargs.get("comment_id", None)
        profile_id = self.kwargs.get("profile_id", None)

        current_profile = request.current_profile
        if str(current_profile.id) != str(profile_id):
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if comment_id:
            like = get_object_or_404(
                CommentLike, profile=current_profile, comment=comment_id
            )
            self.perform_destroy(like)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_400_BAD_REQUEST)


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class ListCommentRepliesView(generics.ListAPIView):
    """Get replies to a comment."""

    serializer_class = CommentDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()
    pagination_class = CommentRepliesPagination

    def get_queryset(self):
        comment_id = self.kwargs.get("comment_id")
        replies = Comment.objects.filter(Q(parent_comment=comment_id)).order_by(
            "created_at"
        )
        return replies


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
    post=extend_schema(parameters=[auth_profile_param]),
)
class ListCreateSavedPostView(generics.ListCreateAPIView):
    serializer_class = CreateSavedPostSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SavedPost.objects.all()
    pagination_class = ListProfilePostsPagination

    def get_queryset(self):
        profile_id = self.request.headers["auth-profile-id"]
        profile = Profile.objects.get(id=profile_id)

        saved_posts = profile.saved_posts.all()
        saved_posts_ordered = saved_posts.order_by("-saved_at")
        posts = [obj.post for obj in saved_posts_ordered]
        return posts

    def get_serializer_class(self):
        if self.request.method == "GET":
            return PostDetailedSerializer
        return CreateSavedPostSerializer

    def get(self, request, *args, **kwargs):
        profile_id = self.request.headers["auth-profile-id"]
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if not user_profile_match:
            return Response(
                {"message": "Profile does not belong to the authenticated user."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        profile_id = request.data["profile"]
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()
        # ensure profile creating saved post belongs to the authenticated user
        if not user_profile_match:
            return Response(
                {"message": "Profile does not belong to the authenticated user."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().post(request, *args, **kwargs)


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class DestroySavedPostView(generics.DestroyAPIView):
    """Delete a SavedPost."""

    serializer_class = CreateSavedPostSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SavedPost.objects.all()

    def destroy(self, request, *args, **kwargs):
        post_id = self.kwargs.get("post_id", None)
        profile_id = self.request.headers["auth-profile-id"]

        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if not user_profile_match:
            return Response(
                {"message": "Profile does not belong to the authenticated user."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if post_id:
            like = get_object_or_404(
                SavedPost, profile=user_profile_match, post=post_id
            )
            self.perform_destroy(like)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_400_BAD_REQUEST)


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
    pagination_class = ReportReasonPagination

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
    retrieve=extend_schema(parameters=[auth_profile_param]),
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

    def get_queryset(self):
        requesting_profile = self.request.current_profile
        if self.request.user.is_staff:
            return PostReport.objects.all()
        return PostReport.objects.filter(reporter=requesting_profile)

    def get_serializer_class(self):
        if self.action == "create":
            return CreatePostReportSerializer
        return PostReportDetailSerializer

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context["request"] = self.request
        return context

    @extend_schema(parameters=[auth_profile_param])
    @action(detail=True, methods=["post"], permission_classes=[permissions.IsAdminUser])
    def resolve(self, request, pk=None):
        """
        Endpoint for staff to resolve a report
        """
        resolving_profile = request.current_profile

        report = self.get_object()
        resolution_note = request.data.get("resolution_note", "")
        request_status = request.data.get("status", PostReport.ReportStatus.RESOLVED)

        if request_status not in dict(PostReport.ReportStatus.choices):
            return Response(
                {"error": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST
            )

        report.status = request_status
        report.resolution_note = resolution_note
        report.resolved_by = resolving_profile
        report.save()

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
