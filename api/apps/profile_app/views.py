"""
Views for the profile api.
"""

from rest_framework import generics, permissions, status, serializers
from apps.profile_app.models import Profile, ProfileImage, PetType
from .serializers import (
    ProfileSerializer,
    ProfileCreateSerializer,
    ProfileUpdateSerializer,
    ProfileImageSerializer,
    ProfileDetailedSerializer,
    PetTypeSerializer,
    SearchProfileSerializer,
    ProfileImageUploadUrlRequestSerializer,
    ProfileImageUploadUrlResponseSerializer,
    ConfirmProfileImageUploadRequestSerializer,
)
from rest_framework.response import Response
import logging
from django.shortcuts import get_object_or_404
from django.db.models import Q, Exists, OuterRef
from apps.interactions_app.models import Follow, FollowRequest
from django.db import transaction
from apps.posts_app.pagination import SearchedProfilesPagination
from drf_spectacular.utils import extend_schema_view, extend_schema

from core.schema_params import auth_profile_param, username_param
from apps.core_app.storage_utils import (
    generate_profile_original_key,
    generate_presigned_upload_url,
    check_s3_object_exists,
)
from apps.core_app.tasks import process_profile_image_task

logger = logging.getLogger(__name__)


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreateProfileView(generics.CreateAPIView):
    """Create a new Profile in the system."""

    serializer_class = ProfileCreateSerializer
    queryset = Profile.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        try:
            # Make request data mutable and add user ID
            mutable_data = request.data.copy()
            mutable_data["user"] = self.request.user.id

            # Create serializer with mutable data
            serializer = self.get_serializer(data=mutable_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)

            logger.info(f"Profile created: {serializer.data['username']} for user {request.user.id}")

            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )

        except Exception as e:
            logger.error(f"Error creating profile: {str(e)}")
            if isinstance(e, serializers.ValidationError):
                errors = {}
                # handle unique username constraint error with custom error message
                if "username" in str(e):
                    errors["username"] = [
                        "A profile with that username already exists."
                    ]

                if len(errors):
                    return Response(errors, status=status.HTTP_400_BAD_REQUEST)

                # handle other validation errors
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

            return Response(
                {"message": "Error creating profile."},
                status=status.HTTP_400_BAD_REQUEST,
            )


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
    patch=extend_schema(parameters=[auth_profile_param]),
    delete=extend_schema(parameters=[auth_profile_param]),
)
class RetrieveUpdateDestroyProfileView(generics.RetrieveAPIView, generics.UpdateAPIView, generics.DestroyAPIView):
    """Retrieve, update or delete a Profile."""

    queryset = Profile.objects.select_related('regularprofile', 'businessprofile').all()
    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    allowed_methods = ["GET", "PATCH", "DELETE"]
    lookup_url_kwarg = "public_id"
    lookup_field = "public_id"

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProfileDetailedSerializer
        elif self.request.method == "PATCH":
            return ProfileUpdateSerializer
        return ProfileSerializer

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        serializer = self.get_serializer(instance, context={"request": request})
        return Response(serializer.data)

    def update(self, request, *args, **kwargs):
        public_id = self.kwargs.get("public_id")
        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(public_id=public_id).first()
        if not user_profile_match:
            logger.warning(
                f"Unauthorized profile update attempt: "
                f"profile {public_id} does not belong to user {request.user.id}"
            )
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            partial = kwargs.pop("partial", False)
            instance = self.get_object()
            serializer = self.get_serializer(instance, data=request.data, partial=partial)
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)

            if getattr(instance, "_prefetched_objects_cache", None):
                # If 'prefetch_related' has been applied to a queryset, we need to
                # forcibly invalidate the prefetch cache on the instance.
                instance._prefetched_objects_cache = {}
            
            # Refresh instance from database to get updated values
            instance.refresh_from_db()
            instance_serializer = ProfileSerializer(instance)
            logger.info(f"Profile {public_id} updated successfully")
            return Response(instance_serializer.data)
        except Exception as e:
            logger.error(f"Error updating profile {public_id}: {str(e)}")
            return Response(
                {"error": "Failed to update profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        public_id = self.kwargs.get("public_id")

        # Ensure the profile belongs to the current authenticated user
        try:
            profile = self.request.user.profiles.get(public_id=public_id)
        except Profile.DoesNotExist:
            return Response(
                {
                    "error": "Profile not found or you don't have permission to delete it"
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # Prevent deleting the last profile
        if self.request.user.profiles.count() <= 1:
            return Response(
                {
                    "error": "Cannot delete your only profile. At least one profile is required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            if hasattr(profile, "image"):
                profile.image.delete()

            # Delete the profile
            profile.delete()
            logger.info(
                f"Profile {public_id} deleted successfully by user {request.user.email}"
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"Error deleting profile {public_id}: {str(e)}")
            return Response(
                {"error": "Failed to delete profile. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreateProfileImageView(generics.CreateAPIView):
    """Create a new profile image for a profile."""

    serializer_class = ProfileImageSerializer
    permission_classes = [permissions.IsAuthenticated]
    allowed_methods = ["POST"]
    queryset = ProfileImage.objects.all()

    def create(self, request, *args, **kwargs):
        profile_id = request.data.get("profileId", None)
        image = request.FILES.get("image")

        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if not user_profile_match:
            logger.warning(
                f"Unauthorized profile image creation: "
                f"profile {profile_id} does not belong to user {request.user.id}"
            )
            return Response(status=status.HTTP_400_BAD_REQUEST)
        
        if not image:
            logger.warning(f"Profile image creation attempted without image file")
            return Response(
                {"error": "Image file is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            image_serializer = self.get_serializer(
                data={"profile": user_profile_match.id, "image": image}
            )
            image_serializer.is_valid(raise_exception=True)
            self.perform_create(image_serializer)

            logger.info(f"Profile image created for profile {profile_id}")

            headers = self.get_success_headers(image_serializer.data)
            return Response(
                image_serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
        except Exception as e:
            logger.error(
                f"Error creating profile image for profile {profile_id}: {str(e)}",
                exc_info=True
            )
            return Response(
                {"error": "Failed to create profile image"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


@extend_schema_view(
    patch=extend_schema(parameters=[auth_profile_param]),
)
class UpdateProfileImageView(generics.UpdateAPIView):
    """Update profile image for a profile."""

    serializer_class = ProfileImageSerializer
    permission_classes = [permissions.IsAuthenticated]
    allowed_methods = ["PATCH"]
    queryset = ProfileImage.objects.all()
    lookup_url_kwarg = "public_id"
    lookup_field = "public_id"

    def patch(self, request, *args, **kwargs):
        profile_id = request.data.get("profileId", None)
        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()

        if not user_profile_match:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                instance = self.get_object()
                # Store reference to old image
                old_image = instance.image if instance.image else None

                # Update with new image
                response = self.partial_update(request, *args, **kwargs)

                # If update was successful and there was an old image, delete it
                if response.status_code == 200:
                    if old_image:
                        old_image.delete(save=False)
                    logger.info(f"Profile image updated for profile {instance.profile_id}")

                return response

        except Exception as e:
            logger.error(f"Error updating profile image: {str(e)}")
            return Response(
                {"error": "Failed to update profile image."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


@extend_schema_view(
    post=extend_schema(
        parameters=[auth_profile_param],
        request=ProfileImageUploadUrlRequestSerializer,
        responses={200: ProfileImageUploadUrlResponseSerializer},
    ),
)
class ProfileImageUploadUrlView(generics.GenericAPIView):
    """
    Return a presigned URL for uploading a profile image directly to R2.
    Use for both new and update flows. Frontend should PUT the file to upload_url,
    then call confirm-upload with the returned key.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        # Frontend sends camelCase profileId; normalize for serializer
        if "profileId" in data and "profile_id" not in data:
            data["profile_id"] = data["profileId"]
        serializer = ProfileImageUploadUrlRequestSerializer(data=data)
        if not serializer.is_valid():
            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST,
            )
        profile_id = serializer.validated_data["profile_id"]
        user_profile = request.user.profiles.filter(id=profile_id).first()
        if not user_profile:
            logger.warning(
                f"Unauthorized profile image upload URL: "
                f"profile {profile_id} does not belong to user {request.user.id}"
            )
            return Response(
                {"error": "Profile not found or you do not own it."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        key = generate_profile_original_key(user_profile.public_id)
        presigned = generate_presigned_upload_url(key, expires_in=3600)
        if presigned is None:
            logger.error("Failed to generate presigned URL for profile image")
            return Response(
                {"error": "Failed to generate upload URL."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
        return Response(
            {
                "upload_url": presigned["url"],
                "key": presigned["key"],
                "expires_in": 3600,
            },
            status=status.HTTP_200_OK,
        )


@extend_schema_view(
    post=extend_schema(
        parameters=[auth_profile_param],
        request=ConfirmProfileImageUploadRequestSerializer,
        responses={200: ProfileImageSerializer, 201: ProfileImageSerializer},
    ),
)
class ConfirmProfileImageUploadView(generics.GenericAPIView):
    """
    Confirm that the frontend has uploaded a file to the presigned URL.
    Creates or updates ProfileImage and queues background processing.
    """

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        # Frontend sends camelCase profileId; normalize for serializer
        if "profileId" in data and "profile_id" not in data:
            data["profile_id"] = data["profileId"]

        serializer = ConfirmProfileImageUploadRequestSerializer(data=data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        profile_id = serializer.validated_data["profile_id"]
        key = serializer.validated_data["key"]
        user_profile = request.user.profiles.filter(id=profile_id).first()

        if not user_profile:
            logger.warning(
                f"Unauthorized confirm upload: profile {profile_id} does not belong to user {request.user.id}"
            )
            return Response(
                {"error": "Profile not found or you do not own it."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if not check_s3_object_exists(key):
            return Response(
                {"error": "Upload not found at the given key. Upload the file first."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                profile_image = getattr(user_profile, "image", None)
                created = False
                if profile_image is None:
                    profile_image = ProfileImage.objects.create(
                        profile=user_profile,
                        original_key=key,
                        processing_status=ProfileImage.ProcessingStatus.UPLOADED,
                    )
                    created = True
                else:
                    profile_image.original_key = key
                    profile_image.processing_status = ProfileImage.ProcessingStatus.UPLOADED
                    profile_image.save(update_fields=["original_key", "processing_status"])

                def queue_task():
                    process_profile_image_task.delay(profile_image.id)

                transaction.on_commit(queue_task)

            profile_image.refresh_from_db()
            response_serializer = ProfileImageSerializer(
                profile_image,
                context={"request": request},
            )
            return Response(
                response_serializer.data,
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error confirming profile image upload: {str(e)}", exc_info=True)
            return Response(
                {"error": "Failed to confirm upload."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ListPetTypesView(generics.ListAPIView):
    """List Pet Type options."""

    serializer_class = PetTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = PetType.objects.all()
    pagination_class = None

    def get_queryset(self):
        options = PetType.objects.all().order_by("name")
        return options


@extend_schema_view(
    get=extend_schema(parameters=[username_param, auth_profile_param]),
)
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
        current_profile = self.request.current_profile
        username = self.request.query_params.get("username", None)
        profiles = Profile.objects.filter(
            Q(username__icontains=username) & ~Q(id=current_profile.id)
        ).annotate(
            _is_following=Exists(
                Follow.objects.filter(
                    followed=OuterRef('pk'),
                    followed_by=current_profile
                )
            ),
            _follows_you=Exists(
                Follow.objects.filter(
                    followed_by=OuterRef('pk'),
                    followed=current_profile
                )
            ),
            _has_requested_follow=Exists(
                FollowRequest.objects.filter(
                    target=OuterRef('pk'),
                    requester=current_profile
                )
            ),
        ).order_by("username")
        return profiles

    def get_serializer_context(self):
        current_profile = self.request.current_profile
        return {
            "profile_id": current_profile.id,
            "request": self.request,
        }

