"""
Views for the posts api.
"""

from rest_framework import generics, permissions
from rest_framework import status
from apps.core_app.models import (
    Post,
    PostImage,
    Profile,
    Like,
    Comment,
    Follow,
    CommentLike,
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
)
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
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
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if not caption or not profile_id or not user_profile_match:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # create post
                data = {
                    "caption": caption,
                    "profile": user_profile_match.id,
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


class CreateLikeView(generics.CreateAPIView):
    """Create or delete a Like."""

    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Like.objects.all()

    def create(self, request, *args, **kwargs):
        post_id = self.kwargs.get("post_id", None)
        profile_id = request.data["profileId"]
        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if not user_profile_match:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # prevent profile from liking own post
        post = get_object_or_404(Post, pk=post_id)
        if post.profile.id == user_profile_match.id:
            return Response(status=status.HTTP_403_FORBIDDEN)

        new_like_data = {
            "post": post_id,
            "profile": user_profile_match.id,
        }
        serializer = self.get_serializer(data=new_like_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class DestroyLikeView(generics.DestroyAPIView):
    """Delete a Like."""

    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Like.objects.all()

    def destroy(self, request, *args, **kwargs):
        post_id = self.kwargs.get("pk", None)
        profile_id = self.kwargs.get("profile_id", None)

        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if post_id and user_profile_match:
            like = get_object_or_404(Like, profile=user_profile_match, post=post_id)
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
        profile_posts = Post.objects.filter(profile__id=profile_id).order_by(
            "-created_at"
        )
        return profile_posts


class RetrieveProfileView(generics.RetrieveAPIView):
    """Get details of a Profile."""

    serializer_class = ProfileDetailsSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)


class RetrieveFeedView(generics.ListAPIView):
    """List feed posts from profiles that the authenticated profile follows."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()

    def get(self, request, *args, **kwargs):
        profile_id = self.kwargs.get("id", None)
        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()
        if not user_profile_match:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        requesting_profile_id = self.kwargs.get("id", None)
        posts = Post.objects.filter(
            profile__following__followed_by=requesting_profile_id
        ).order_by("-created_at")
        return posts


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

        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if not user_profile_match:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        serializer = self.get_serializer(
            data={
                "text": text,
                "post": post_id,
                "profile": user_profile_match.id,
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
        auth_profile_id = request.headers["auth-profile-id"]
        instance = self.get_object()

        # check that the user requesting the delete owns the post
        if instance.profile.user != self.request.user:
            return Response(
                {"error": "Requesting user does not own this resource."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # check that the profile requesting the delete owns the post
        if instance.profile.id != int(auth_profile_id):
            return Response(
                {"error": "Requesting profile does not own this resource."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                "username",
                OpenApiTypes.STR,
                description="Username string or substring to search.",
            ),
        ]
    )
)
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


class CreateFollowView(generics.CreateAPIView):
    """Create a follow."""

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    def create(self, request, *args, **kwargs):
        auth_profile_id = self.kwargs.get("id")

        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(
            id=auth_profile_id
        ).first()

        if not user_profile_match:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        profile_to_follow = get_object_or_404(Profile, pk=request.data["profileId"])
        # profile cannon follow itself
        if profile_to_follow.id == user_profile_match.id:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        new_follow_data = {
            "followed": request.data["profileId"],
            "followed_by": user_profile_match.id,
        }
        serializer = self.get_serializer(data=new_follow_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                "username",
                OpenApiTypes.STR,
                description="Username string or substring to search.",
            ),
        ]
    )
)
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


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                "username",
                OpenApiTypes.STR,
                description="Username string or substring to search.",
            ),
        ]
    )
)
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


class DestroyFollowView(generics.DestroyAPIView):
    """Delete a follow."""

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    def destroy(self, request, *args, **kwargs):
        profile_id = self.kwargs.get("pk")  # profile id to unfollow
        auth_profile_id = self.kwargs.get("auth_profile_id")

        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(
            id=auth_profile_id
        ).first()

        if not user_profile_match:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if profile_id and user_profile_match:
            follow = get_object_or_404(
                Follow, followed_by=user_profile_match.id, followed=profile_id
            )
            self.perform_destroy(follow)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_400_BAD_REQUEST)


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
            ~Q(profile=profile_id) & Q(id__gt=post_id)
        ).order_by("-created_at")
        return posts


class CreateCommentLikeView(generics.CreateAPIView):
    """Create or delete a Comment Like."""

    serializer_class = CommentLikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CommentLike.objects.all()

    def create(self, request, *args, **kwargs):
        comment_id = self.kwargs.get("comment_id", None)
        profile_id = request.data["profileId"]
        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if not user_profile_match:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        new_like_data = {
            "comment": comment_id,
            "profile": user_profile_match.id,
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


class DestroyCommentLikeView(generics.DestroyAPIView):
    """Delete a Comment Like."""

    serializer_class = CommentLikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = CommentLike.objects.all()

    def destroy(self, request, *args, **kwargs):
        comment_id = self.kwargs.get("comment_id", None)
        profile_id = self.kwargs.get("profile_id", None)

        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if comment_id and user_profile_match:
            like = get_object_or_404(
                CommentLike, profile=user_profile_match, comment=comment_id
            )
            self.perform_destroy(like)
            return Response(status=status.HTTP_204_NO_CONTENT)
        return Response(status=status.HTTP_400_BAD_REQUEST)


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
