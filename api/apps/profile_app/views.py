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
)
from rest_framework.response import Response
import logging
from django.shortcuts import get_object_or_404
from django.db.models import Q
from django.db import transaction
from apps.posts_app.pagination import SearchedProfilesPagination
from drf_spectacular.utils import extend_schema_view, extend_schema

from core.schema_params import auth_profile_param, username_param

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
        profile_id = self.kwargs.get("pk")
        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()
        if not user_profile_match:
            logger.warning(
                f"Unauthorized profile update attempt: "
                f"profile {profile_id} does not belong to user {request.user.id}"
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
            logger.info(f"Profile {profile_id} updated successfully")
            return Response(instance_serializer.data)
        except Exception as e:
            logger.error(f"Error updating profile {profile_id}: {str(e)}")
            return Response(
                {"error": "Failed to update profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    def destroy(self, request, *args, **kwargs):
        profile_id = self.kwargs.get("pk")

        # Ensure the profile belongs to the current authenticated user
        try:
            profile = self.request.user.profiles.get(id=profile_id)
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
            # Delete associated profile image from storage
            if hasattr(profile, "image"):
                profile.image.image.delete(save=False)
                profile.image.delete()

            # Delete the profile
            profile.delete()
            logger.info(
                f"Profile {profile_id} deleted successfully by user {request.user.email}"
            )

            return Response(status=status.HTTP_204_NO_CONTENT)

        except Exception as e:
            logger.error(f"Error deleting profile {profile_id}: {str(e)}")
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
                    logger.info(f"Profile image updated for profile {profile_id}")

                return response

        except Exception as e:
            logger.error(f"Error updating profile image: {str(e)}")
            return Response(
                {"error": "Failed to update profile image."},
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
        ).order_by("username")
        return profiles

    def get_serializer_context(self):
        current_profile = self.request.current_profile
        return {
            "profile_id": current_profile.id,
            "request": self.request,
        }

