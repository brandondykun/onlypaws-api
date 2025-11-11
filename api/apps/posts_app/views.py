"""
Views for the posts api.
"""

from rest_framework import generics, permissions, status
from apps.posts_app.models import Post, PostImage, SavedPost
from .serializers import (
    PostSerializer,
    PostUpdateSerializer,
    PostImageSerializer,
    PostDetailedSerializer,
    CreateSavedPostSerializer,
)
from rest_framework.response import Response
from rest_framework.parsers import MultiPartParser, FormParser
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import transaction
from .pagination import (
    ListExplorePostsPagination,
    ListProfilePostsPagination,
    ListSimilarPostsPagination,
)
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
)
import logging

from core.schema_params import auth_profile_param

logger = logging.getLogger(__name__)

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


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class RetrieveFeedView(generics.ListAPIView):
    """List feed posts from profiles that the authenticated profile follows."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Post.objects.all()

    def get_queryset(self):
        current_profile = self.request.current_profile

        posts = Post.objects.filter(
            Q(profile__following__followed_by=current_profile)
            & ~Q(reports__reason__id=1)  # filter reported inappropriate content
        ).order_by("-created_at")
        return posts


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
        try:
            post = self.queryset.get(id=post_id)
            logger.debug(f"Post {post_id} retrieved by user {request.user.id}")
            serializer = self.serializer_class(post, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Post.DoesNotExist:
            logger.warning(f"Post {post_id} not found")
            return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

    def update(self, request, *args, **kwargs):
        current_profile = request.current_profile
        instance = self.get_object()
        
        # check that the user requesting the update owns the post
        if instance.profile.user != self.request.user:
            logger.warning(
                f"Unauthorized post update attempt: user {request.user.id} "
                f"attempted to update post {instance.id} owned by user {instance.profile.user.id}"
            )
            return Response(
                {"error": "Requesting user does not own this resource."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # check that the profile requesting the update owns the post
        if instance.profile.id != int(current_profile.id):
            logger.warning(
                f"Unauthorized post update attempt: profile {current_profile.id} "
                f"attempted to update post {instance.id} owned by profile {instance.profile.id}"
            )
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
        logger.info(f"Post {updated_instance.id} updated successfully by profile {current_profile.id}")
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def destroy(self, request, *args, **kwargs):
        current_profile = request.current_profile
        instance = self.get_object()

        # check that the user requesting the delete owns the post
        if instance.profile.user != self.request.user:
            logger.warning(
                f"Unauthorized post deletion attempt: user {request.user.id} "
                f"attempted to delete post {instance.id} owned by user {instance.profile.user.id}"
            )
            return Response(
                {"error": "Requesting user does not own this resource."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # check that the profile requesting the delete owns the post
        if instance.profile.id != int(current_profile.id):
            logger.warning(
                f"Unauthorized post deletion attempt: profile {current_profile.id} "
                f"attempted to delete post {instance.id} owned by profile {instance.profile.id}"
            )
            return Response(
                {"error": "Requesting profile does not own this resource."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        logger.info(f"Post {instance.id} deleted by profile {current_profile.id}")
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


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
        current_profile = self.request.current_profile

        posts = Post.objects.filter(
            ~Q(profile__following__followed_by=current_profile)
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
    get=extend_schema(parameters=[auth_profile_param]),
    post=extend_schema(parameters=[auth_profile_param]),
)
class ListCreateSavedPostView(generics.ListCreateAPIView):
    serializer_class = CreateSavedPostSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = SavedPost.objects.all()
    pagination_class = ListProfilePostsPagination

    def get_queryset(self):
        current_profile = self.request.current_profile
        saved_posts = current_profile.saved_posts.all()
        saved_posts_ordered = saved_posts.order_by("-saved_at")
        posts = [obj.post for obj in saved_posts_ordered]
        return posts

    def get_serializer_class(self):
        if self.request.method == "GET":
            return PostDetailedSerializer
        return CreateSavedPostSerializer

    def post(self, request, *args, **kwargs):
        current_profile = request.current_profile
        profile_id = request.data.get("profile")
        # ensure profile creating saved post belongs to the authenticated user
        if str(profile_id) != str(current_profile.id):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        try:
            response = super().post(request, *args, **kwargs)
            if response.status_code == 201:
                post_id = request.data.get("post")
                logger.info(f"Post {post_id} saved by profile {profile_id}")
            return response
        except Exception as e:
            logger.error(f"Error saving post for profile {profile_id}: {str(e)}")
            return Response(
                {"error": "Failed to save post"},
                status=status.HTTP_400_BAD_REQUEST
            )


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
        current_profile = request.current_profile

        if post_id:
            try:
                saved_post = get_object_or_404(
                    SavedPost, profile=current_profile, post=post_id
                )
                self.perform_destroy(saved_post)
                logger.info(f"Post {post_id} unsaved by profile {current_profile.id}")
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                logger.error(
                    f"Error unsaving post {post_id} for profile {current_profile.id}: {str(e)}"
                )
                return Response(status=status.HTTP_400_BAD_REQUEST)
        
        logger.warning(f"Unsave attempt with no post_id by profile {current_profile.id}")
        return Response(status=status.HTTP_400_BAD_REQUEST)


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
