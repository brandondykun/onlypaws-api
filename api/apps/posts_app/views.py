"""
Views for the posts api.
"""

from rest_framework import generics, permissions, mixins, status, viewsets
from rest_framework.decorators import action
from apps.user_app.models import Profile
from apps.posts_app.models import Post, PostImage, SavedPost
from apps.interactions_app.models import Like, Comment, Follow, CommentLike
from apps.moderation_app.models import ReportReason, PostReport
from .serializers import (
    PostSerializer,
    PostUpdateSerializer,
    PostImageSerializer,
    LikeSerializer,
    CommentSerializer,
    PostDetailedSerializer,
    CommentDetailedSerializer,
    CommentChainSerializer,
    SearchProfileSerializer,
    FollowSerializer,
    CommentLikeSerializer,
    CreateSavedPostSerializer,
    PostReportDetailSerializer,
    CreatePostReportSerializer,
    ReportReasonSerializer,
)
from ..user_app.serializers import ProfileSerializer, ProfileDetailedSerializer
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
    ReportPostsPagination,
)
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
)
import logging

logger = logging.getLogger(__name__)

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
        contains_ai = request.data.get("aiGenerated", False)
        images = request.FILES.getlist("images")
        orders = request.POST.getlist("order")

        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile
        if str(profile_id) != str(current_profile.id) or not caption:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # Validate that images and orders match in length
        if len(images) != len(orders):
            logger.error("Number of images and order values must match.")
            return Response(
                {"error": "Number of images and order values must match."},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():
                # create post
                data = {
                    "caption": caption,
                    "profile": current_profile.id,
                    "contains_ai": contains_ai,
                }
                serializer = self.serializer_class(data=data)
                serializer.is_valid(raise_exception=True)
                self.perform_create(serializer)

                new_post = Post.objects.get(id=serializer.data["id"])

                # Create PostImage objects with order
                for image, order in zip(images, orders):
                    PostImage.objects.create(
                        image=image,
                        post=new_post,
                        order=int(order)
                    )
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
            logger.error(f"Error creating post: {str(e)}")
            return Response(
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

    serializer_class = ProfileDetailedSerializer
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
    patch=extend_schema(parameters=[auth_profile_param]),
    put=extend_schema(parameters=[auth_profile_param]),
)
class RetrieveUpdateDestroyPostView(generics.RetrieveUpdateDestroyAPIView):
    """Get, update, or delete details of a Post."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()

    def get(self, request, *args, **kwargs):
        post_id = self.kwargs.get("pk")
        post = self.queryset.get(id=post_id)
        serializer = self.serializer_class(post, context={"request": request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    def update(self, request, *args, **kwargs):
        current_profile = request.current_profile
        instance = self.get_object()
        
        # check that the user requesting the update owns the post
        if instance.profile.user != self.request.user:
            return Response(
                {"error": "Requesting user does not own this resource."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # check that the profile requesting the update owns the post
        if instance.profile.id != int(current_profile.id):
            return Response(
                {"error": "Requesting profile does not own this resource."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only allow updating the caption field
        allowed_fields = {'caption'}
        update_data = {k: v for k, v in request.data.items() if k in allowed_fields}
        
        if not update_data:
            return Response(
                {"error": "No valid fields provided for update. Only 'caption' can be updated."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Use PostUpdateSerializer for updates to ensure proper validation
        serializer = PostUpdateSerializer(instance, data=update_data, partial=True)
        serializer.is_valid(raise_exception=True)
        
        # Save the updated instance
        updated_instance = serializer.save()
        
        # Refresh from database to ensure we have the latest data
        updated_instance.refresh_from_db()

        # Return the updated post using PostDetailedSerializer
        response_serializer = PostDetailedSerializer(updated_instance, context={"request": request})
        return Response(response_serializer.data, status=status.HTTP_200_OK)

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
    queryset = Profile.objects.select_related('regularprofile', 'businessprofile').all()
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
    """Get posts that are visually similar to the desired post using image embeddings."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()
    pagination_class = ListSimilarPostsPagination

    def get_queryset(self):
        post_id = self.kwargs.get("pk")
        profile_id = self.request.GET.get("profileId")
        min_similarity = float(self.request.GET.get("min_similarity", 0.3))

        try:
            # Get the post and its main image
            post: Post = get_object_or_404(Post, id=post_id)
            main_image: PostImage = post.images.first()

            if (
                not main_image
                or main_image.embedding is None
                or (
                    hasattr(main_image.embedding, "__len__")
                    and len(main_image.embedding) == 0
                )
            ):
                # Fallback to basic filtering if no embedding available
                return Post.objects.filter(
                    ~Q(profile__user=self.request.user)
                    & Q(id__gt=post_id)
                    & ~Q(reports__reason__id=1)
                ).order_by("-created_at")[:20]

            # Find similar images
            similar_images = main_image.find_similar_images(
                limit=100, min_similarity=min_similarity
            )

            # Get posts for similar images, preserving similarity order and ensuring uniqueness
            similar_posts_ids = []
            seen_post_ids = set()
            for img in similar_images:
                # Does the post belong to any profile of the requesting user?
                is_own_post = img.post.profile.user == self.request.user
                # Is the post the original post passed in kwargs?
                is_original_post = img.post.id == post_id

                # Skip if it's the user's own post or the original post
                if is_own_post or is_original_post:
                    continue

                # Only add if we haven't seen this post before
                if img.post.id not in seen_post_ids:
                    similar_posts_ids.append(img.post.id)
                    seen_post_ids.add(img.post.id)

            if not similar_posts_ids:
                return Post.objects.none()

            # Get posts and filter out reported content
            posts_dict = (
                Post.objects.filter(id__in=similar_posts_ids)
                .exclude(reports__reason__id=1)  # filter reported inappropriate content
                .exclude(id=post_id)
                .in_bulk(field_name="id")
            )

            # Return posts in similarity order (preserving the order from similar_images)
            ordered_posts = []
            for post_id in similar_posts_ids:
                if post_id in posts_dict:
                    ordered_posts.append(posts_dict[post_id])

            return ordered_posts

        except Exception as e:
            # Log error and return empty queryset
            logger.error(f"Error in ListSimilarPostsView: {str(e)}")
            return Post.objects.none()


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
)
class CommentChainRetrieveView(generics.GenericAPIView):
    """
    Retrieve a comment with its entire parent comment chain.
    
    This view optimizes database queries by:
    1. Fetching the target comment with select_related for profile and post
    2. Collecting all parent comment IDs in a single traversal using only('parent_comment_id')
    3. Fetching all parent comments in a single query with select_related('profile')
    4. Including circular reference protection to handle data corruption
    
    The response includes the target comment and a parent_chain field containing
    all ancestor comments ordered from root (oldest) to immediate parent.
    
    Endpoint: GET /api/comments/<pk>/chain/
    """

    serializer_class = CommentChainSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Comment.objects.all()

    def get(self, request, *args, **kwargs):
        """
        Handle GET request to retrieve comment with parent chain.
        
        Query optimization strategy:
        - Query 1: Fetch target comment with profile and post
        - Query 2: Collect parent IDs using only('reply_to_comment_id') - minimal data transfer
        - Query 3: Bulk fetch all parents with select_related('profile')
        
        This results in exactly 3 queries regardless of chain depth.
        """
        comment_id = self.kwargs.get("pk")
        
        # Step 1: Fetch the target comment with related profile and post
        # This is Query #1
        comment = get_object_or_404(
            Comment.objects.select_related("profile", "post"),
            pk=comment_id
        )
        
        # Step 2: Collect all parent comment IDs by traversing up the chain
        # This is Query #2 - uses only() to minimize data transfer
        # NOTE: We traverse via reply_to_comment (immediate parent), not parent_comment (top-level root)
        parent_ids = []
        current_id = comment.reply_to_comment_id
        seen_ids = set([comment.id])  # Circular reference protection
        max_depth = 100  # Safety limit to prevent infinite loops
        depth = 0
        
        while current_id and depth < max_depth:
            if current_id in seen_ids:
                # Circular reference detected - log and break
                logger.warning(
                    f"Circular reference detected in comment chain at comment_id={current_id}"
                )
                break
            
            seen_ids.add(current_id)
            parent_ids.append(current_id)
            
            # Fetch only the reply_to_comment_id field to minimize data transfer
            parent = Comment.objects.filter(id=current_id).only("reply_to_comment_id").first()
            
            if not parent:
                # Parent comment doesn't exist (data inconsistency)
                logger.warning(
                    f"Parent comment {current_id} not found - possible data inconsistency"
                )
                break
            
            current_id = parent.reply_to_comment_id
            depth += 1
        
        # Step 3: Bulk fetch all parent comments in a single query
        # This is Query #3 - fetches all parents with their profiles
        if parent_ids:
            parent_comments = Comment.objects.filter(
                id__in=parent_ids
            ).select_related("profile", "post")
            
            # Create a lookup dictionary for efficient access
            parent_lookup = {p.id: p for p in parent_comments}
            
            # Attach parent comments to the target comment for serializer access
            # This allows the serializer to access prefetched data efficiently
            current = comment
            for parent_id in parent_ids:
                if parent_id in parent_lookup:
                    current.parent_comment = parent_lookup[parent_id]
                    current = current.parent_comment
        
        # Serialize and return the comment with its parent chain
        serializer = self.get_serializer(comment)
        return Response(serializer.data, status=status.HTTP_200_OK)


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


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class DestroyPostImageView(generics.DestroyAPIView):
    """Delete a PostImage."""

    serializer_class = PostImageSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = PostImage.objects.all()

    def destroy(self, request, *args, **kwargs):
        post_image_id = self.kwargs.get("pk")
        current_profile = request.current_profile

        # Get the PostImage instance
        post_image = get_object_or_404(PostImage, pk=post_image_id)

        # Check that the user requesting the delete owns the post
        if post_image.post.profile.user != self.request.user:
            message = "Requesting user does not own this resource."
            logger.error(f"Delete post image failed: {message}")
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)

        # Check that the profile requesting the delete owns the post
        if post_image.post.profile.id != int(current_profile.id):
            message= "Requesting profile does not own this resource."
            logger.error(f"Delete post image failed: {message}")
            return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)

        # Check if this is the last image of the post
        post = post_image.post
        if post.images.count() <= 1:
            message = "Cannot delete the last image of a post. Delete the entire post instead."
            logger.error(f"Delete post image failed: {message}")
            return Response({"error": message}, status=status.HTTP_400_BAD_REQUEST)

        # Delete the PostImage - the signal handler will clean up storage
        self.perform_destroy(post_image)
        logger.info(f"Post image {post_image.id} deleted successfully")
        return Response(status=status.HTTP_204_NO_CONTENT)
