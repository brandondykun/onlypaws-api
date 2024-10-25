"""
Views for the user api.
"""

from rest_framework import generics, permissions
from rest_framework.settings import api_settings
from rest_framework import status
from apps.core_app.models import Profile, User, ProfileImage
from .serializers import (
    UserSerializer,
    ProfileDetailedSerializer,
    ProfileSerializer,
    UserProfileSerializer,
    ProfileImageSerializer,
    ProfileCreateSerializer,
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
                "about": None,
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


class SearchCreateProfileView(generics.ListCreateAPIView):
    """Create a new Profile in the system or search for a profile by username."""

    serializer_class = ProfileSerializer
    queryset = Profile.objects.all()
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):

        username = request.query_params.get("username", None)

        if not username:
            return Response(
                {"message": "Must provide a username query param."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        profiles = Profile.objects.filter(username__icontains=username)
        serializer = self.serializer_class(profiles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class RetrieveUpdateProfileView(generics.RetrieveUpdateAPIView):
    """Retrieve or update a Profile."""

    ## TODO: update can only be done by own profile

    queryset = Profile.objects.all()
    serializer_class = ProfileDetailedSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "GET":
            return ProfileDetailedSerializer
        return ProfileSerializer


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


class CreateUpdateProfileImageView(generics.CreateAPIView, generics.UpdateAPIView):
    """Create a new profile image for a profile."""

    serializer_class = ProfileImageSerializer
    permission_classes = [permissions.IsAuthenticated]
    allowed_methods = ["POST", "PATCH"]
    queryset = ProfileImage.objects.all()

    def create(self, request, *args, **kwargs):
        profile = request.user.profile
        image = request.FILES.get("image")

        if not image:
            return Response(status=status.HTTP_400_BAD_REQUEST)

        image_serializer = self.get_serializer(
            data={"profile": profile.id, "image": image}
        )
        image_serializer.is_valid(raise_exception=True)
        self.perform_create(image_serializer)

        headers = self.get_success_headers(image_serializer.data)
        return Response(
            image_serializer.data, status=status.HTTP_201_CREATED, headers=headers
        )
