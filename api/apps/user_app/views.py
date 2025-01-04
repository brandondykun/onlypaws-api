"""
Views for the user api.
"""

from rest_framework import generics, permissions
from rest_framework.settings import api_settings
from rest_framework import status
from apps.core_app.models import Profile, User, ProfileImage, PetType
from .serializers import (
    UserSerializer,
    ProfileDetailedSerializer,
    ProfileSerializer,
    UserProfileSerializer,
    ProfileImageSerializer,
    ProfileCreateSerializer,
    PetTypeSerializer,
    ProfileUpdateSerializer,
)
from rest_framework.response import Response
import logging

# Create a logger for this file
logger = logging.getLogger(__file__)


class CreateUserView(generics.CreateAPIView):
    """Create a new user in the system."""

    serializer_class = UserSerializer
    permission_classes = []
    authentication_classes = []
    allowed_methods = ["POST"]

    def create(self, request, *args, **kwargs):
        username = request.data.get("username", None)
        email = request.data.get("email", None)
        password = request.data.get("password", None)

        if not username or not email or not password:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        # TODO: Do this in a transaction
        # create User
        user_serializer = self.get_serializer(
            data={"email": email, "password": password}
        )
        user_serializer.is_valid(raise_exception=True)
        self.perform_create(user_serializer)
        # create Profile
        profile_serializer = ProfileCreateSerializer(
            data={
                "username": username,
                "user": user_serializer.data["id"],
                "about": "",
                "name": "",
                "breed": "",
            }
        )
        profile_serializer.is_valid(raise_exception=True)
        self.perform_create(profile_serializer)

        user = User.objects.get(id=user_serializer.data["id"])
        response_serializer = UserProfileSerializer(user)

        headers = self.get_success_headers(response_serializer.data)
        return Response(
            response_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )


class RetrieveUpdateUserView(generics.RetrieveUpdateAPIView):
    """Manage the authenticated user."""

    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Retrieve and return authenticated user."""
        return self.request.user


class CreateProfileView(generics.CreateAPIView):
    """Create a new Profile in the system."""

    serializer_class = ProfileCreateSerializer
    queryset = Profile.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, *args, **kwargs):
        # make request data mutable
        request.data._mutable = True
        request.data["user"] = self.request.user.id
        request.data._mutable = False
        return self.create(request, *args, **kwargs)


class RetrieveUpdateProfileView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a Profile."""

    queryset = Profile.objects.all()
    serializer_class = ProfileDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]
    allowed_methods = ["PATCH"]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProfileDetailedSerializer
        elif self.request.method == "PATCH":
            return ProfileUpdateSerializer
        return ProfileSerializer

    def update(self, request, *args, **kwargs):
        profile_id = self.kwargs.get("pk")
        # ensure that the profile sent belongs to the current authenticated user
        user_profile_match = self.request.user.profiles.filter(id=profile_id).first()
        if not user_profile_match:
            return Response(status=status.HTTP_400_BAD_REQUEST)

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
        return Response(instance_serializer.data)


class RetrieveUserInfoView(generics.RetrieveAPIView):
    """Retrieve logged in user's profile."""

    queryset = User.objects.all()
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        user = self.request.user
        serializer = self.serializer_class(user, context={"request": request})
        logger.info(f"{user.email} retrieved their info.")
        return Response(serializer.data, status=status.HTTP_200_OK)


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

        if not user_profile_match or not image:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        image_serializer = self.get_serializer(
            data={"profile": user_profile_match.id, "image": image}
        )
        image_serializer.is_valid(raise_exception=True)
        self.perform_create(image_serializer)

        headers = self.get_success_headers(image_serializer.data)
        return Response(
            image_serializer.data, status=status.HTTP_201_CREATED, headers=headers
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

        return self.partial_update(request, *args, **kwargs)


class ListPetTypesView(generics.ListAPIView):
    """List Pet Type options."""

    serializer_class = PetTypeSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = PetType.objects.all()
    pagination_class = None

    def get_queryset(self):
        options = PetType.objects.all().order_by("name")
        return options
