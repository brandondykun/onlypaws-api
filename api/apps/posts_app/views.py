"""
Views for the posts api.
"""

from rest_framework import generics, permissions, status
from apps.posts_app.models import Post, PostImage, SavedPost, PostImageTag
from apps.profile_app.models import Profile as ProfileModel
from apps.interactions_app.models import Follow
from .serializers import (
    PostUpdateSerializer,
    PostImageSerializer,
    PostDetailedSerializer,
    CreateSavedPostSerializer,
    CreatePostImageTagSerializer,
    PostImageTagSerializer,
    PrepareUploadRequestSerializer,
    PrepareUploadResponseSerializer,
    CompletePostSerializer,
)
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from django.shortcuts import get_object_or_404
from django.db.models import Q, Case, When, Count
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
import json

from core.schema_params import auth_profile_param
from apps.core_app.storage_utils import generate_presigned_upload_url, generate_original_image_key
from apps.moderation_app.block_utils import get_blocked_profile_ids, are_profiles_blocking
from apps.moderation_app.models import INAPPROPRIATE_REPORT_REASON_NAME
from apps.recommendations_app.pagination import ExploreCursorPagination

logger = logging.getLogger(__name__)


VALID_ASPECT_RATIOS = Post.AspectRatio.values


def _delete_pending_post_placeholders(post):
    """
    Delete a post that is still in PENDING_UPLOAD state after a failed complete-post.
    Cascade deletes PostImages; post_delete signals remove original_key (and image) from R2.
    Called on any error so the frontend can safely restart the workflow from prepare-upload.
    """
    if post.status != Post.Status.PENDING_UPLOAD:
        return
    post_id, public_id = post.id, post.public_id
    post.delete()
    logger.info(f"Deleted PENDING_UPLOAD post {post_id} ({public_id}) after failed completion.")


def adjust_tag_position_for_center_crop(x_percent, y_percent, original_width, original_height, target_aspect_ratio=Post.AspectRatio.SQUARE):
    """
    Adjust tag position percentages to account for center crop to target aspect ratio.
    
    The crop_to_aspect_ratio_and_resize function crops images to the target ratio:
    - If image is wider than target ratio: crops equally from left and right
    - If image is taller than target ratio: crops equally from top and bottom
    - If image matches target ratio: no cropping needed
    
    Args:
        x_percent: X position as percentage (0-100) of original width
        y_percent: Y position as percentage (0-100) of original height
        original_width: Original image width in pixels
        original_height: Original image height in pixels
        target_aspect_ratio: Target aspect ratio string (e.g., Post.AspectRatio.SQUARE, Post.AspectRatio.PORTRAIT)
    
    Returns:
        tuple: (adjusted_x_percent, adjusted_y_percent) for the cropped image
    """
    # Parse target aspect ratio
    w_ratio, h_ratio = map(int, target_aspect_ratio.split(':'))
    target_ratio = w_ratio / h_ratio  # e.g., 4/5 = 0.8 for 4:5
    
    # Calculate original ratio
    original_ratio = original_width / original_height
    
    # Check if ratios match (within floating point tolerance)
    if abs(original_ratio - target_ratio) < 0.001:
        # Image already matches target ratio - no adjustment needed
        return x_percent, y_percent
    
    if original_ratio > target_ratio:
        # Image is wider than target - crop left and right
        # New width based on keeping full height
        new_width = original_height * target_ratio
        crop_amount = (original_width - new_width) / 2
        
        # Convert x_percent to pixels, adjust, then back to percent of new width
        original_x_px = (x_percent / 100) * original_width
        new_x_px = original_x_px - crop_amount
        new_x_percent = (new_x_px / new_width) * 100
        
        # Y position doesn't change (still percent of same height)
        return new_x_percent, y_percent
    else:
        # Image is taller than target - crop top and bottom
        # New height based on keeping full width
        new_height = original_width / target_ratio
        crop_amount = (original_height - new_height) / 2
        
        # Convert y_percent to pixels, adjust, then back to percent of new height
        original_y_px = (y_percent / 100) * original_height
        new_y_px = original_y_px - crop_amount
        new_y_percent = (new_y_px / new_height) * 100
        
        # X position doesn't change (still percent of same width)
        return x_percent, new_y_percent


@extend_schema_view(
    post=extend_schema(
        parameters=[auth_profile_param],
        request=PrepareUploadRequestSerializer,
        responses={201: PrepareUploadResponseSerializer},
    ),
)
class PrepareUploadView(generics.CreateAPIView):
    """
    Prepare a new post for image uploads via presigned URLs.
    
    This endpoint creates a post placeholder and returns presigned URLs
    for uploading images directly to cloud storage. After uploading,
    the client should call PATCH /post/{id}/ to complete the post.
    """

    serializer_class = PrepareUploadRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        current_profile = request.current_profile
        
        # Validate request
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid prepare-upload request: {serializer.errors}")
            return Response(
                {"error": "Invalid request.", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        image_count = serializer.validated_data["image_count"]
        
        try:
            with transaction.atomic():
                # Create post placeholder with PENDING_UPLOAD status
                post = Post.objects.create(
                    profile=current_profile,
                    caption="",  # Will be set when completing the post
                    status=Post.Status.PENDING_UPLOAD,
                )
                
                # Create PostImage placeholders and generate presigned URLs
                upload_urls = []
                for order in range(image_count):
                    # Create PostImage placeholder
                    post_image = PostImage.objects.create(
                        post=post,
                        order=order,
                        processing_status=PostImage.ProcessingStatus.PENDING_UPLOAD,
                    )
                    
                    # Generate S3 key for original image
                    key = generate_original_image_key(post.public_id, order)
                    
                    # Store the original key in the PostImage
                    post_image.original_key = key
                    post_image.save(update_fields=["original_key"])
                    
                    # Generate presigned upload URL
                    presigned = generate_presigned_upload_url(key, expires_in=3600)
                    
                    if presigned is None:
                        logger.error(f"Failed to generate presigned URL for post {post.id}, image {order}")
                        # Rollback by raising an exception
                        raise ValueError("Failed to generate presigned upload URL")
                    
                    upload_urls.append({
                        "url": presigned["url"],
                        "key": presigned["key"],
                        "order": order,
                    })
                
                logger.info(
                    f"Created post placeholder {post.id} with {image_count} image slots "
                    f"for profile {current_profile.id}"
                )
                
                return Response(
                    {
                        "post_id": post.id,
                        "post_public_id": str(post.public_id),
                        "upload_urls": upload_urls,
                    },
                    status=status.HTTP_201_CREATED
                )
        
        except ValueError as e:
            logger.error(f"Error preparing upload: {str(e)}")
            return Response(
                {"error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        except Exception as e:
            logger.error(f"Unexpected error preparing upload: {str(e)}")
            return Response(
                {"error": "Failed to prepare upload."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ListProfilePostsView(generics.ListAPIView):
    """List all posts from a profile."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ListProfilePostsPagination

    def list(self, request, *args, **kwargs):
        """Override list to check profile access before queryset evaluation."""

        public_id = self.kwargs.get("public_id", None)
        current_profile = request.current_profile
        target_profile = get_object_or_404(ProfileModel, public_id=public_id)

        # Check if profiles are blocking each other
        if are_profiles_blocking(current_profile, target_profile):
            return Response(
                {"detail": "Not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if target_profile.is_private:
            is_own_profile = target_profile.id == current_profile.id
            is_following = Follow.objects.filter(
                followed=target_profile,
                followed_by=current_profile
            ).exists()

            if not is_own_profile and not is_following:
                return Response(
                    {"detail": "This profile is private."},
                    status=status.HTTP_403_FORBIDDEN
                )

        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        public_id = self.kwargs.get("public_id", None)
        current_profile = self.request.current_profile

        profile_posts = Post.objects.filter(Q(profile__public_id=public_id)).prefetch_related(
            'images__tags__tagged_profile__image',
            'images__tags__tagged_profile__regularprofile',
            'images__tags__tagged_profile__businessprofile',
            'images__tags__tagged_by_profile__image',
            'images__tags__tagged_by_profile__regularprofile',
            'images__tags__tagged_by_profile__businessprofile',
            'profile__image',
            'profile__regularprofile',
            'profile__businessprofile',
            'reports',
        )

        if str(public_id) == str(current_profile.public_id):
            # Don't filter inappropriate posts or pending posts if profile is requesting their own posts
            return profile_posts.order_by("-created_at")

        # For other profiles, only show READY posts and filter reported inappropriate content
        return profile_posts.filter(
            Q(status=Post.Status.READY) & ~Q(reports__reason__name=INAPPROPRIATE_REPORT_REASON_NAME)
        ).order_by("-created_at")


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

        heavily_reported_ids = ProfileModel.objects.annotate(
            _arc=Count(
                "profile_reports",
                filter=Q(profile_reports__status__in=["PENDING", "UNDER_REVIEW"]),
            )
        ).filter(_arc__gte=5).values("id")

        blocked_ids = get_blocked_profile_ids(current_profile)

        posts = Post.objects.filter(
            Q(profile__following__followed_by=current_profile)
            & Q(status=Post.Status.READY)  # only show completed posts
            & ~Q(reports__reason__name=INAPPROPRIATE_REPORT_REASON_NAME)  # filter reported inappropriate content
        ).exclude(
            profile_id__in=heavily_reported_ids
        ).exclude(
            profile_id__in=blocked_ids
        ).prefetch_related(
            'images__tags__tagged_profile__image',
            'images__tags__tagged_profile__regularprofile',
            'images__tags__tagged_profile__businessprofile',
            'images__tags__tagged_by_profile__image',
            'images__tags__tagged_by_profile__regularprofile',
            'images__tags__tagged_by_profile__businessprofile',
            'profile__image',
            'profile__regularprofile',
            'profile__businessprofile',
            'reports',
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
    lookup_url_kwarg = "public_id"
    lookup_field = "public_id"
    queryset = Post.objects.prefetch_related(
        'images__tags__tagged_profile__image',
        'images__tags__tagged_profile__regularprofile',
        'images__tags__tagged_profile__businessprofile',
        'images__tags__tagged_by_profile__image',
        'images__tags__tagged_by_profile__regularprofile',
        'images__tags__tagged_by_profile__businessprofile',
        'profile__image',
        'profile__regularprofile',
        'profile__businessprofile',
        'reports',
    ).all()

    def get(self, request, *args, **kwargs):
        public_id = self.kwargs.get("public_id")
        try:
            post = self.queryset.get(public_id=public_id)

            # Check if post author is blocked
            current_profile = request.current_profile
            if current_profile and are_profiles_blocking(current_profile, post.profile):
                return Response({"error": "Post not found"}, status=status.HTTP_404_NOT_FOUND)

            logger.debug(f"Post {public_id} retrieved by user {request.user.id}")
            serializer = self.serializer_class(post, context={"request": request})
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Post.DoesNotExist:
            logger.warning(f"Post {public_id} not found")
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

        # Handle completing a pending upload post
        if instance.status == Post.Status.PENDING_UPLOAD:
            return self._complete_pending_post(request, instance, current_profile)
        
        # For READY posts, only allow updating caption and contains_ai
        if instance.status != Post.Status.READY:
            return Response(
                {"error": f"Cannot update post with status '{instance.status}'."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Only allow updating the caption field
        allowed_fields = {'caption', 'contains_ai'}
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
        
        # If caption was updated, regenerate combined embedding
        if 'caption' in update_data:
            try:
                updated_instance.queue_combined_embedding_generation(countdown=5)
                logger.info(f"Queued combined embedding regeneration for Post {updated_instance.id} after caption update")
            except Exception as e:
                # Don't fail the update if embedding queue fails
                logger.error(f"Failed to queue combined embedding for updated Post {updated_instance.id}: {str(e)}")
        
        # Refresh from database to ensure we have the latest data with prefetched relations
        updated_instance = Post.objects.prefetch_related(
            'images__tags__tagged_profile__image',
            'images__tags__tagged_profile__regularprofile',
            'images__tags__tagged_profile__businessprofile',
            'images__tags__tagged_by_profile__image',
            'images__tags__tagged_by_profile__regularprofile',
            'images__tags__tagged_by_profile__businessprofile',
            'profile__image',
            'profile__regularprofile',
            'profile__businessprofile',
            'reports',
        ).get(id=updated_instance.id)

        # Return the updated post using PostDetailedSerializer
        response_serializer = PostDetailedSerializer(updated_instance, context={"request": request})
        logger.info(f"Post {updated_instance.id} updated successfully by profile {current_profile.id}")
        return Response(response_serializer.data, status=status.HTTP_200_OK)

    def _complete_pending_post(self, request, instance, current_profile):
        """
        Complete a post that was created via prepare-upload.
        
        This method handles the PATCH request to finalize a post after
        images have been uploaded to cloud storage.
        """
        # Validate the completion request
        serializer = CompletePostSerializer(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid post completion request: {serializer.errors}")
            _delete_pending_post_placeholders(instance)
            return Response(
                {"error": "Invalid request.", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        validated_data = serializer.validated_data
        caption = validated_data["caption"]
        aspect_ratio = validated_data.get("aspect_ratio", Post.AspectRatio.SQUARE)
        ai_generated = validated_data.get("ai_generated", False)
        tags_data = validated_data.get("tags") or {}
        
        # Validate aspect ratio
        if aspect_ratio not in VALID_ASPECT_RATIOS:
            logger.error(f"Invalid aspect ratio: {aspect_ratio}")
            _delete_pending_post_placeholders(instance)
            return Response(
                {"error": f"Invalid aspect ratio. Must be one of: {', '.join(VALID_ASPECT_RATIOS)}"},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            with transaction.atomic():
                # Update post with provided data
                instance.caption = caption
                instance.aspect_ratio = aspect_ratio
                instance.contains_ai = ai_generated
                instance.status = Post.Status.PROCESSING
                instance.save(update_fields=["caption", "aspect_ratio", "contains_ai", "status"])
                
                # Update PostImage statuses to UPLOADED (they should have original_key set)
                post_images = list(instance.images.all().order_by("order"))
                
                for post_image in post_images:
                    if not post_image.original_key:
                        logger.warning(
                            f"PostImage {post_image.id} has no original_key set"
                        )
                    post_image.processing_status = PostImage.ProcessingStatus.UPLOADED
                    post_image.save(update_fields=["processing_status"])
                
                # Process tags if provided
                if tags_data:
                    self._process_tags(tags_data, post_images, current_profile, aspect_ratio)
                
                # Queue background processing task
                transaction.on_commit(
                    lambda: self._queue_image_processing(instance.id)
                )
                
                logger.info(
                    f"Post {instance.id} marked for processing with {len(post_images)} images "
                    f"by profile {current_profile.id}"
                )
                
                # Refresh and return the post
                updated_instance = Post.objects.prefetch_related(
                    'images__tags__tagged_profile__image',
                    'images__tags__tagged_profile__regularprofile',
                    'images__tags__tagged_profile__businessprofile',
                    'images__tags__tagged_by_profile__image',
                    'images__tags__tagged_by_profile__regularprofile',
                    'images__tags__tagged_by_profile__businessprofile',
                    'profile__image',
                    'profile__regularprofile',
                    'profile__businessprofile',
                    'reports',
                ).get(id=instance.id)
                
                response_serializer = PostDetailedSerializer(
                    updated_instance, context={"request": request}
                )
                return Response(response_serializer.data, status=status.HTTP_200_OK)
        
        except ValueError as e:
            logger.error(f"Validation error completing post {instance.id}: {str(e)}")
            _delete_pending_post_placeholders(instance)
            return Response(
                {"error": str(e)},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as e:
            logger.error(f"Error completing post {instance.id}: {str(e)}")
            _delete_pending_post_placeholders(instance)
            return Response(
                {"error": "Failed to complete post."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def _process_tags(self, tags_data, post_images, current_profile, aspect_ratio):
        """Process and create PostImageTag objects for the post images."""
        
        for post_image in post_images:
            img_idx_str = str(post_image.order)
            if img_idx_str not in tags_data:
                continue
            
            image_tags = tags_data[img_idx_str]
            if not isinstance(image_tags, list):
                raise ValueError(f"Tags for image {post_image.order} must be a list.")
            
            for tag_data in image_tags:
                # Validate tag data structure
                required_fields = ["taggedProfileId", "xPosition", "yPosition", "originalWidth", "originalHeight"]
                if not all(field in tag_data for field in required_fields):
                    raise ValueError(
                        f"Each tag must include: {', '.join(required_fields)}"
                    )
                
                # Validate profile exists
                try:
                    tagged_profile = ProfileModel.objects.get(id=tag_data["taggedProfileId"])
                except ProfileModel.DoesNotExist:
                    raise ValueError(
                        f"Profile {tag_data['taggedProfileId']} does not exist."
                    )
                
                # Adjust tag position to account for cropping
                original_width = tag_data["originalWidth"]
                original_height = tag_data["originalHeight"]
                x_position = tag_data["xPosition"]
                y_position = tag_data["yPosition"]
                
                adjusted_x, adjusted_y = adjust_tag_position_for_center_crop(
                    x_position,
                    y_position,
                    original_width,
                    original_height,
                    target_aspect_ratio=aspect_ratio
                )
                
                # Create the tag with adjusted positions
                PostImageTag.objects.create(
                    post_image=post_image,
                    tagged_profile=tagged_profile,
                    tagged_by_profile=current_profile,
                    x_position=adjusted_x,
                    y_position=adjusted_y
                )
                logger.info(
                    f"Created tag for profile {tagged_profile.id} "
                    f"in image {post_image.id} at original ({x_position}, {y_position}), "
                    f"adjusted to ({adjusted_x:.2f}, {adjusted_y:.2f})"
                )

    def _queue_image_processing(self, post_id):
        """Queue the background task to process post images."""
        try:
            from apps.core_app.tasks import process_post_images_task
            
            task = process_post_images_task.delay(post_id)
            logger.info(f"Queued image processing task {task.id} for Post {post_id}")
        except Exception as e:
            logger.error(f"Failed to queue image processing task for Post {post_id}: {str(e)}")

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

        # Note: Image files are deleted via post_delete signals after successful DB deletion
        logger.info(f"Post {instance.id} deleted by profile {current_profile.id}")
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    get=extend_schema(
        parameters=[
            auth_profile_param,
            OpenApiParameter(
                "cursor",
                OpenApiTypes.STR,
                description=(
                    "Opaque cursor returned in the previous response's `next` link. "
                    "Omit on the first request."
                ),
            ),
        ]
    ),
)
class ListExplorePostsView(generics.ListAPIView):
    """
    Personalized explore feed.

    Returns posts ranked by similarity to the requesting profile's preference
    embedding (long-term taste blended with short-term intent), filtered to
    public, READY posts the user does not already follow / own / block. Cold-
    start users (no usable signal) get a popularity-ranked fallback.

    Pagination is cursor-based; the `next` link in each response advances
    through a materialized batch of recommendations.
    """

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ExploreCursorPagination
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "explore_feed"
    queryset = Post.objects.none()

    def list(self, request, *args, **kwargs):
        paginator = self.paginator
        post_ids = paginator.paginate_for_profile(request.current_profile, request)

        if not post_ids:
            return paginator.get_paginated_response([])

        preserved_order = Case(*[When(pk=pk, then=pos) for pos, pk in enumerate(post_ids)])
        qs = (
            Post.objects
            .filter(id__in=post_ids)
            .prefetch_related(
                'images__tags__tagged_profile__image',
                'images__tags__tagged_profile__regularprofile',
                'images__tags__tagged_profile__businessprofile',
                'images__tags__tagged_by_profile__image',
                'images__tags__tagged_by_profile__regularprofile',
                'images__tags__tagged_by_profile__businessprofile',
                'profile__image',
                'profile__regularprofile',
                'profile__businessprofile',
                'reports',
            )
            .order_by(preserved_order)
        )
        serializer = self.get_serializer(qs, many=True)
        return paginator.get_paginated_response(serializer.data)


@extend_schema_view(
    get=extend_schema(
        parameters=[
            OpenApiParameter(
                "min_similarity",
                OpenApiTypes.FLOAT,
                description="Minimum similarity threshold (0-1). Default is 0.3.",
            ),
        ]
    )
)
class ListSimilarPostsView(generics.ListAPIView):
    """
    Return up to 100 visually similar posts with:
    - Max 3 posts from the same profile as the original post
    - Excludes the user's own posts
    - Excludes posts reported for inappropriate content
    """

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ListSimilarPostsPagination
    queryset = Post.objects.all()

    # How many posts from DB to pull before filtering in Python
    PRE_LIMIT = 300
    MAX_RESULTS = 100
    MAX_SAME_PROFILE = 3

    def get_queryset(self):
        public_id = self.kwargs.get("public_id")
        min_similarity = float(self.request.query_params.get("min_similarity", 0.3))
        current_profile = self.request.current_profile
        blocked_ids = get_blocked_profile_ids(current_profile)

        try:
            # Get the post
            post: Post = get_object_or_404(Post, public_id=public_id)

            # Build the base filter for private profiles:
            # Include posts from:
            # - Public profiles
            # - Private profiles that the current user follows
            private_profile_filter = (
                Q(profile__is_private=False) |  # Public profiles
                Q(profile__following__followed_by=current_profile)  # Private profiles user follows
            )

            # -------------------------------
            # 1. Handle case with no embedding
            # -------------------------------
            if not post.has_combined_embedding():
                return (
                    Post.objects.filter(
                        ~Q(profile__user=self.request.user),
                        id__gt=post.id,
                        status=Post.Status.READY,  # only show completed posts
                    )
                    .filter(private_profile_filter)
                    .exclude(reports__reason__name=INAPPROPRIATE_REPORT_REASON_NAME)
                    .exclude(profile_id__in=blocked_ids)
                    .prefetch_related(
                        'images__tags__tagged_profile__image',
                        'images__tags__tagged_profile__regularprofile',
                        'images__tags__tagged_profile__businessprofile',
                        'images__tags__tagged_by_profile__image',
                        'images__tags__tagged_by_profile__regularprofile',
                        'images__tags__tagged_by_profile__businessprofile',
                        'profile__image',
                        'profile__regularprofile',
                        'profile__businessprofile',
                        'reports',
                    )
                    .distinct()
                    .order_by("-created_at")[: self.MAX_RESULTS]
                )

            # -------------------------------
            # 2. Use vector similarity search
            # -------------------------------
            qs = (
                post.find_similar_posts(min_similarity=min_similarity)
                .filter(~Q(profile__user=self.request.user))
                .filter(private_profile_filter)
                .filter(status=Post.Status.READY)  # only show completed posts
                .exclude(reports__reason__name=INAPPROPRIATE_REPORT_REASON_NAME)
                .exclude(profile_id__in=blocked_ids)
                .distinct()
            )

            # --------------------------------------------
            # 3. Pre-limit BEFORE iterating (performance!)
            # --------------------------------------------
            # Pull enough posts to enforce uniqueness rules
            qs = qs[: self.PRE_LIMIT]

            # Materialize only the pre-limited subset
            posts = list(qs)

            # --------------------------------------------
            # 4. Enforce "max 3 posts from same profile"
            # --------------------------------------------
            source_profile_id = post.profile_id
            same_profile_count = 0
            final_posts = []

            for p in posts:
                if p.profile_id == source_profile_id:
                    if same_profile_count < self.MAX_SAME_PROFILE:
                        final_posts.append(p)
                        same_profile_count += 1
                else:
                    final_posts.append(p)

                # Stop early if we already have enough
                if len(final_posts) >= self.MAX_RESULTS:
                    break

            if not final_posts:
                return Post.objects.none()

            # --------------------------------------------
            # 5. Convert back to queryset with preserved order
            # --------------------------------------------
            post_ids = [p.id for p in final_posts]

            preserved_order = Case(
                *[When(pk=pk, then=pos) for pos, pk in enumerate(post_ids)]
            )

            return (
                Post.objects.filter(id__in=post_ids)
                .prefetch_related(
                    'images__tags__tagged_profile__image',
                    'images__tags__tagged_profile__regularprofile',
                    'images__tags__tagged_profile__businessprofile',
                    'images__tags__tagged_by_profile__image',
                    'images__tags__tagged_by_profile__regularprofile',
                    'images__tags__tagged_by_profile__businessprofile',
                    'profile__image',
                    'profile__regularprofile',
                    'profile__businessprofile',
                    'reports',
                )
                .order_by(preserved_order)[: self.MAX_RESULTS]
            )

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
        saved_posts = current_profile.saved_posts.all().order_by("-saved_at")
        # Extract post IDs to maintain order
        post_ids = [obj.post_id for obj in saved_posts]
        blocked_ids = get_blocked_profile_ids(current_profile)

        # Build queryset with prefetching and preserve order
        preserved_order = Case(
            *[When(pk=pk, then=pos) for pos, pk in enumerate(post_ids)]
        )

        return Post.objects.filter(id__in=post_ids).exclude(
            profile_id__in=blocked_ids
        ).prefetch_related(
            'images__tags__tagged_profile__image',
            'images__tags__tagged_profile__regularprofile',
            'images__tags__tagged_profile__businessprofile',
            'images__tags__tagged_by_profile__image',
            'images__tags__tagged_by_profile__regularprofile',
            'images__tags__tagged_by_profile__businessprofile',
            'profile__image',
            'profile__regularprofile',
            'profile__businessprofile',
            'reports',
        ).order_by(preserved_order)

    def get_serializer_class(self):
        if self.request.method == "GET":
            return PostDetailedSerializer
        return CreateSavedPostSerializer

    def post(self, request, *args, **kwargs):
        current_profile = request.current_profile
        data = request.data.copy()
        post_input = data.get("post_public_id") or data.get("post")
        if isinstance(post_input, str):
            try:
                post = Post.objects.get(public_id=post_input)
                data["post"] = post.id
            except Post.DoesNotExist:
                return Response(
                    {"error": "Post not found."},
                    status=status.HTTP_404_NOT_FOUND,
                )
        profile_id = data.get("profile")
        if profile_id is not None and str(profile_id) != str(current_profile.id):
            return Response(status=status.HTTP_400_BAD_REQUEST)
        try:
            serializer = self.get_serializer(data=data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            logger.info(f"Post {data.get('post')} saved by profile {profile_id or current_profile.id}")
            return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)
        except Exception as e:
            logger.error(f"Error saving post for profile {profile_id or current_profile.id}: {str(e)}")
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
        post_public_id = self.kwargs.get("post_public_id", None)
        current_profile = request.current_profile

        if post_public_id:
            try:
                post = get_object_or_404(Post, public_id=post_public_id)
                saved_post = get_object_or_404(
                    SavedPost, profile=current_profile, post=post
                )
                self.perform_destroy(saved_post)
                logger.info(f"Post {post_public_id} unsaved by profile {current_profile.id}")
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                logger.error(
                    f"Error un-saving post {post_public_id} for profile {current_profile.id}: {str(e)}"
                )
                return Response(status=status.HTTP_400_BAD_REQUEST)
        
        logger.warning(f"Unsave attempt with no post_public_id by profile {current_profile.id}")
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
        public_id = self.kwargs.get("public_id")
        current_profile = request.current_profile

        # Get the PostImage instance
        post_image = get_object_or_404(PostImage, public_id=public_id)

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

        # Note: Image files are deleted via post_delete signal after successful DB deletion
        self.perform_destroy(post_image)
        logger.info(f"Post image {post_image.id} deleted successfully")
        return Response(status=status.HTTP_204_NO_CONTENT)


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreatePostImageTagView(generics.CreateAPIView):
    """Create a new PostImageTag."""

    serializer_class = CreatePostImageTagSerializer
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        current_profile = request.current_profile

        # Validate input data
        serializer = self.serializer_class(data=request.data)
        if not serializer.is_valid():
            logger.error(f"Invalid tag data: {serializer.errors}")
            return Response(
                {"error": "Invalid tag data.", "details": serializer.errors},
                status=status.HTTP_400_BAD_REQUEST
            )

        validated_data = serializer.validated_data
        post_image_id = validated_data["post_image_id"]
        tagged_profile_id = validated_data["tagged_profile_id"]
        x_position = validated_data["x_position"]
        y_position = validated_data["y_position"]
        original_width = validated_data["original_width"]
        original_height = validated_data["original_height"]

        try:
            # Get the post image
            post_image = PostImage.objects.get(id=post_image_id)

            # Check that the requesting user owns the post
            if post_image.post.profile.user != request.user:
                logger.warning(
                    f"Unauthorized tag creation attempt: user {request.user.id} "
                    f"attempted to tag in post {post_image.post.id} owned by user {post_image.post.profile.user.id}"
                )
                return Response(
                    {"error": "Only the post owner can add tags."},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Check that the requesting profile owns the post
            if post_image.post.profile.id != int(current_profile.id):
                logger.warning(
                    f"Unauthorized tag creation attempt: profile {current_profile.id} "
                    f"attempted to tag in post {post_image.post.id} owned by profile {post_image.post.profile.id}"
                )
                return Response(
                    {"error": "Only the post owner can add tags."},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Get the tagged profile
            tagged_profile = ProfileModel.objects.get(id=tagged_profile_id)

            # Check if tag already exists
            existing_tag = PostImageTag.objects.filter(
                post_image=post_image,
                tagged_profile=tagged_profile
            ).first()

            if existing_tag:
                logger.warning(
                    f"Duplicate tag attempt: profile {tagged_profile.id} "
                    f"already tagged in image {post_image.id}"
                )
                return Response(
                    {"error": f"Profile {tagged_profile.username} is already tagged in this image."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            # Adjust tag position to account for cropping
            # Get the aspect ratio from the post
            post_aspect_ratio = getattr(post_image.post, 'aspect_ratio', Post.AspectRatio.SQUARE)
            adjusted_x, adjusted_y = adjust_tag_position_for_center_crop(
                float(x_position),
                float(y_position),
                original_width,
                original_height,
                target_aspect_ratio=post_aspect_ratio
            )

            # Create the tag
            tag = PostImageTag.objects.create(
                post_image=post_image,
                tagged_profile=tagged_profile,
                tagged_by_profile=current_profile,
                x_position=adjusted_x,
                y_position=adjusted_y
            )

            logger.info(
                f"Created tag {tag.id} for profile {tagged_profile.id} "
                f"in image {post_image.id} by profile {current_profile.id}"
            )

            # Return the created tag
            response_serializer = PostImageTagSerializer(tag, context={'request': request})
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED
            )

        except PostImage.DoesNotExist:
            logger.error(f"Post image {post_image_id} not found")
            return Response(
                {"error": "Post image not found."},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error creating tag: {str(e)}")
            return Response(
                {"error": "Failed to create tag."},
                status=status.HTTP_400_BAD_REQUEST
            )


class ListTaggedPostsView(generics.ListAPIView):
    """List all posts where a specific profile was tagged."""

    serializer_class = PostDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    pagination_class = ListProfilePostsPagination

    def get_queryset(self):
        public_id = self.kwargs.get("public_id", None)
        current_profile = self.request.current_profile
        blocked_ids = get_blocked_profile_ids(current_profile)

        # Check if the target profile is blocked
        try:
            target_profile = ProfileModel.objects.get(public_id=public_id)
            if target_profile.id in blocked_ids:
                return Post.objects.none()
        except ProfileModel.DoesNotExist:
            return Post.objects.none()

        # Build filter for private profiles:
        # Include posts from:
        # - Public profiles
        # - Private profiles that the current user follows
        # - The user's own posts (if they're viewing their own tagged posts)
        private_profile_filter = (
            Q(profile__is_private=False) |  # Public profiles
            Q(profile__following__followed_by=current_profile) |  # Private profiles user follows
            Q(profile=current_profile)  # User's own posts
        )

        # Get posts where the specified profile is tagged in any image
        return Post.objects.filter(
            images__tags__tagged_profile__public_id=public_id
        ).filter(
            private_profile_filter
        ).exclude(
            profile_id__in=blocked_ids
        ).prefetch_related(
            'images__tags__tagged_profile__image',
            'images__tags__tagged_profile__regularprofile',
            'images__tags__tagged_profile__businessprofile',
            'images__tags__tagged_by_profile__image',
            'images__tags__tagged_by_profile__regularprofile',
            'images__tags__tagged_by_profile__businessprofile',
            'profile__image',
            'profile__regularprofile',
            'profile__businessprofile',
            'reports',
        ).distinct().order_by("-created_at")


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class DestroyPostImageTagView(generics.DestroyAPIView):
    """Delete a PostImageTag."""

    serializer_class = PostImageTagSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = PostImageTag.objects.all()

    def destroy(self, request, *args, **kwargs):
        public_id = self.kwargs.get("public_id")
        current_profile = request.current_profile

        try:
            # Get the tag
            tag = get_object_or_404(PostImageTag, public_id=public_id)

            # Check permissions: either the post owner, the person who created the tag,
            # or the tagged profile can delete the tag
            is_post_owner = tag.post_image.post.profile.id == int(current_profile.id)
            is_tag_creator = tag.tagged_by_profile.id == int(current_profile.id)
            is_tagged_profile = tag.tagged_profile.id == int(current_profile.id)

            if not (is_post_owner or is_tag_creator or is_tagged_profile):
                logger.warning(
                    f"Unauthorized tag deletion attempt: profile {current_profile.id} "
                    f"attempted to delete tag {public_id}"
                )
                return Response(
                    {"error": "You don't have permission to delete this tag."},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Delete the tag
            self.perform_destroy(tag)
            logger.info(
                f"Tag {public_id} deleted by profile {current_profile.id} "
                f"(post_owner: {is_post_owner}, creator: {is_tag_creator}, tagged: {is_tagged_profile})"
            )
            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"Error deleting tag {public_id}: {str(e)}")
            return Response(
                {"error": "Failed to delete tag."},
                status=status.HTTP_400_BAD_REQUEST
            )
