"""
Views for the profile api.
"""

from rest_framework import generics, permissions, status, serializers
from apps.profile_app.models import Profile, ProfileImage, PetType
from apps.interactions_app.models import Follow
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
from apps.posts_app.pagination import (
    SearchedProfilesPagination,
    FollowListPagination,
)
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
    OpenApiTypes,
)

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


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class CreateFollowView(generics.CreateAPIView):
    """Create a follow."""

    serializer_class = serializers.ModelSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    class serializer_class(serializers.ModelSerializer):
        class Meta:
            model = Follow
            fields = ['id', 'followed', 'followed_by', 'created_at']
            read_only_fields = ['id', 'created_at']

    def create(self, request, *args, **kwargs):
        auth_profile_id = self.kwargs.get("id")

        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile
        if str(current_profile.id) != str(auth_profile_id):
            logger.warning(
                f"Profile mismatch in follow creation: "
                f"current profile {current_profile.id}, auth profile {auth_profile_id}"
            )
            return Response(status=status.HTTP_400_BAD_REQUEST)

        profile_to_follow_id = request.data.get("profileId")
        profile_to_follow = get_object_or_404(Profile, pk=profile_to_follow_id)
        
        # profile cannot follow itself
        if profile_to_follow.id == current_profile.id:
            logger.warning(f"Profile {current_profile.id} attempted to follow itself")
            return Response(status=status.HTTP_400_BAD_REQUEST)

        try:
            new_follow_data = {
                "followed": profile_to_follow_id,
                "followed_by": current_profile.id,
            }
            serializer = self.get_serializer(data=new_follow_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            headers = self.get_success_headers(serializer.data)
            
            logger.info(
                f"Follow created: profile {current_profile.id} now follows {profile_to_follow_id}"
            )
            
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )
        except Exception as e:
            logger.error(
                f"Error creating follow from {current_profile.id} to {profile_to_follow_id}: {str(e)}"
            )
            return Response(
                {"error": "Failed to create follow"},
                status=status.HTTP_400_BAD_REQUEST
            )


@extend_schema_view(
    get=extend_schema(parameters=[username_param, auth_profile_param]),
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

        try:
            profile = Profile.objects.get(id=profile_id)
            followers_objs = profile.following.all()
            if username:
                followers_objs = followers_objs.filter(
                    Q(followed_by__username__icontains=username)
                )
            sorted_objs = followers_objs.order_by("followed_by__username")
            followers = [obj.followed_by for obj in sorted_objs]
            return followers
        except Profile.DoesNotExist:
            logger.error(f"Profile {profile_id} not found when listing followers")
            return []


@extend_schema_view(
    get=extend_schema(parameters=[username_param, auth_profile_param]),
)
class  ListFollowingView(generics.ListAPIView):
    """List Profiles that a given Profile follows."""

    serializer_class = ProfileSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Profile.objects.all()
    pagination_class = FollowListPagination

    def get_queryset(self):
        profile_id = self.kwargs.get("id", None)
        username = self.request.query_params.get("username", None)

        try:
            profile = Profile.objects.get(id=profile_id)
            following_objs = profile.followers.all()
            if username:
                following_objs = following_objs.filter(
                    Q(followed__username__icontains=username)
                )
            sorted_objs = following_objs.order_by("followed__username")
            following = [obj.followed for obj in sorted_objs]
            return following
        except Profile.DoesNotExist:
            logger.error(f"Profile {profile_id} not found when listing following")
            return []


@extend_schema_view(
    delete=extend_schema(parameters=[auth_profile_param]),
)
class DestroyFollowView(generics.DestroyAPIView):
    """Delete a follow."""

    serializer_class = serializers.ModelSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Follow.objects.all()

    class serializer_class(serializers.ModelSerializer):
        class Meta:
            model = Follow
            fields = ['id', 'followed', 'followed_by', 'created_at']

    def destroy(self, request, *args, **kwargs):
        profile_id = self.kwargs.get("pk")  # profile id to unfollow
        auth_profile_id = self.kwargs.get("auth_profile_id")

        # ensure that the profile sent belongs to the current authenticated user
        current_profile = request.current_profile
        if str(auth_profile_id) != str(current_profile.id):
            logger.warning(
                f"Unauthorized unfollow attempt: profile mismatch "
                f"{auth_profile_id} vs {current_profile.id}"
            )
            return Response(status=status.HTTP_400_BAD_REQUEST)

        if profile_id:
            try:
                follow = get_object_or_404(
                    Follow, followed_by=auth_profile_id, followed=profile_id
                )
                self.perform_destroy(follow)
                logger.info(
                    f"Unfollow: profile {auth_profile_id} unfollowed {profile_id}"
                )
                return Response(status=status.HTTP_204_NO_CONTENT)
            except Exception as e:
                logger.error(
                    f"Error unfollowing: profile {auth_profile_id} -> {profile_id}: {str(e)}"
                )
                return Response(status=status.HTTP_400_BAD_REQUEST)
        
        logger.warning(f"Unfollow attempt with no profile_id by profile {auth_profile_id}")
        return Response(status=status.HTTP_400_BAD_REQUEST)

