"""
Views for the posts api.
"""

from rest_framework import generics, permissions
from rest_framework import status
from apps.core_app.models import Post, PostImage, Profile, Like, Comment, Follow
from .serializers import (
    PostSerializer,
    LikeSerializer,
    CommentSerializer,
    ProfileDetailsSerializer,
    PostDetailedSerializer,
    CommentDetailedSerializer,
    SearchProfileSerializer,
    FollowSerializer,
)
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import transaction
from .pagination import (
    SearchedProfilesPagination,
    ListExplorePostsPagination,
    ListProfilePostsPagination,
)


class CreatePostView(generics.CreateAPIView):
    """Create a new Post."""

    serializer_class = PostSerializer
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, *args, **kwargs):
        print("CREATING POST")
        caption = request.data.get("caption", None)
        images = request.FILES.getlist("images")

        if not caption:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # create post
                data = {
                    "caption": caption,
                    "profile": self.request.user.profile.id,
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


class CreateDestroyLikeView(generics.CreateAPIView, generics.DestroyAPIView):
    """Create or delete a Like."""

    serializer_class = LikeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Like.objects.all()

    def create(self, request, *args, **kwargs):
        # prevent profile from liking own post
        post = get_object_or_404(Post, pk=request.data["postId"])
        if post.profile.id == request.user.profile.id:
            return Response(status=status.HTTP_403_FORBIDDEN)

        new_like_data = {
            "post": request.data["postId"],
            "profile": request.user.profile.id,
        }
        serializer = self.get_serializer(data=new_like_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def destroy(self, request, *args, **kwargs):
        post_id = self.kwargs.get("pk")
        profile = self.request.user.profile.id
        if post_id and profile:
            like = Like.objects.get(profile=profile, post=post_id)
            if like:
                self.perform_destroy(like)
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class ListProfilePostsView(generics.ListAPIView):
    """List all posts from a profile."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ListProfilePostsPagination

    def get_queryset(self):
        profile_id = self.request.query_params.get("profileId", None)
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

    def get_queryset(self):
        posts = Post.objects.filter(
            profile__following__followed_by=self.request.user.profile
        ).order_by("-created_at")
        return posts


class CreateCommentView(generics.CreateAPIView):
    """Create a Comment."""

    serializer_class = CommentSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()

    def create(self, request, *args, **kwargs):
        text = request.data["text"]
        post = request.data["post"]
        profile = self.request.user.profile.id
        serializer = self.get_serializer(
            data={"text": text, "post": post, "profile": profile}
        )
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        comment = Comment.objects.get(id=serializer.data["id"])

        res_serializer = CommentDetailedSerializer(comment)
        headers = self.get_success_headers(res_serializer.data)
        return Response(
            res_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class ListPostCommentsView(generics.ListAPIView):
    """List Comments for a Post."""

    serializer_class = CommentDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()

    def get_queryset(self):
        post_id = self.kwargs.get("pk")
        comments = self.queryset.filter(post=post_id).order_by("-created_at")
        return comments


class RetrievePostView(generics.RetrieveAPIView):
    """Get details of a Post."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()

    def get(self, request, *args, **kwargs):
        post_id = self.kwargs.get("pk")
        post = self.queryset.get(id=post_id)
        serializer = self.serializer_class(post, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class ListSearchedProfilesView(generics.ListAPIView):
    """List Profiles based on search text."""

    serializer_class = SearchProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()
    pagination_class = SearchedProfilesPagination

    # TODO: This should use get_queryset and
    def get(self, request, *args, **kwargs):
        username = self.request.query_params.get("username", None)

        if not username:
            return Response(
                {"message": "Must include username query param."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return self.list(request, *args, **kwargs)

    def get_queryset(self):
        username = self.request.query_params.get("username", None)
        profiles = Profile.objects.filter(
            Q(username__icontains=username) & ~Q(user=self.request.user)
        ).order_by("username")
        return profiles


class CreateDestroyFollowView(generics.CreateAPIView, generics.DestroyAPIView):
    """Create or delete a follow."""

    serializer_class = FollowSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    def create(self, request, *args, **kwargs):
        # prevent profile from following itself
        profile_to_follow = get_object_or_404(Profile, pk=request.data["profileId"])
        if profile_to_follow.id == request.user.profile.id:
            return Response(status=status.HTTP_403_FORBIDDEN)

        new_follow_data = {
            "followed": request.data["profileId"],
            "followed_by": request.user.profile.id,
        }
        serializer = self.get_serializer(data=new_follow_data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(
            serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )

    def destroy(self, request, *args, **kwargs):
        profile_id = self.kwargs.get("pk")  # profile id to unfollow
        profile = self.request.user.profile.id  # authenticated user's profile id
        if profile_id and profile:
            follow = Follow.objects.get(followed_by=profile, followed=profile_id)
            if follow:
                self.perform_destroy(follow)
                return Response(status=status.HTTP_204_NO_CONTENT)
            return Response(status=status.HTTP_404_NOT_FOUND)
        return Response(status=status.HTTP_400_BAD_REQUEST)


class ListExplorePostsView(generics.ListAPIView):
    """List explore posts from profiles that the authenticated profile does not follow."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()
    pagination_class = ListExplorePostsPagination

    def get_queryset(self):
        posts = Post.objects.filter(
            ~Q(profile__following__followed_by=self.request.user.profile)
            & ~Q(profile__user=self.request.user)
        ).order_by("-created_at")
        return posts


class ListSimilarPostsView(generics.ListAPIView):
    """Get explore posts that are similar to the desired post."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()

    def get_queryset(self):
        post_id = self.kwargs.get("pk")
        posts = Post.objects.filter(
            ~Q(profile=self.request.user.profile) & Q(id__gt=post_id)
        ).order_by("-created_at")
        return posts
