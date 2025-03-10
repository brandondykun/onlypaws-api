"""
Views for the user api.
"""

from rest_framework import generics, permissions
from rest_framework import status
from apps.core_app.models import (
    Profile,
    User,
    ProfileImage,
    PetType,
    VerifyEmailToken,
    ResetPasswordToken,
)
from apps.core_app.utils import generate_verification_code
from rest_framework import serializers
from .serializers import (
    UserSerializer,
    ProfileDetailedSerializer,
    ProfileSerializer,
    UserProfileSerializer,
    ProfileImageSerializer,
    ProfileCreateSerializer,
    PetTypeSerializer,
    ProfileUpdateSerializer,
    VerifyEmailTokenSerializer,
    ResetPasswordTokenSerializer,
)
from rest_framework.response import Response
import logging
from django.core.mail import send_mail
from django.utils import timezone
from django.db import transaction
from datetime import timedelta
from drf_spectacular.utils import (
    extend_schema_view,
    extend_schema,
    OpenApiParameter,
)
from django.conf import settings


# schema parameter for auth profile id header
auth_profile_param = OpenApiParameter(
    name="auth-profile-id",
    description="Auth profile id",
    required=True,
    type=str,
    location=OpenApiParameter.HEADER,
)

# Create a logger for this file
logger = logging.getLogger(__file__)


# helper function to send verification email
def send_verification_email(user, token):
    """Send verification email to user."""
    subject = "Verify Your OnlyPaws Email"
    message = f"Your verification code is: {token}"
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


def send_reset_password_email(user, token):
    """Send reset password email to user."""
    subject = "Reset Your OnlyPaws Password"
    message = f"Your password reset code is: {token}"
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [user.email],
        fail_silently=False,
    )


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

        try:
            with transaction.atomic():
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

                # create token for verifying email
                token = generate_verification_code()
                verify_email_serializer = VerifyEmailTokenSerializer(
                    data={"user": user.id, "token": token}
                )
                verify_email_serializer.is_valid(raise_exception=True)
                self.perform_create(verify_email_serializer)

                token = VerifyEmailToken.objects.get(
                    id=verify_email_serializer.data["id"]
                )

                # send email with token
                send_verification_email(user, token)

                response_serializer = UserProfileSerializer(user)

                headers = self.get_success_headers(response_serializer.data)
                return Response(
                    response_serializer.data,
                    status=status.HTTP_201_CREATED,
                    headers=headers,
                )
        except Exception as e:
            # If an exception occurs, the transaction will be rolled back
            # and the main object will be deleted.
            logger.info(f"Error creating user: {str(e)}")
            if isinstance(e, serializers.ValidationError):
                errors = {}
                # handle unique email constraint error
                if "email" in str(e):
                    errors["email"] = ["A user with that email already exists."]
                if "password" in str(e):
                    errors["password"] = e.detail["password"]
                # handle unique username constraint error
                if "username" in str(e):
                    errors["username"] = [
                        "A profile with that username already exists."
                    ]

                if len(errors):
                    return Response(errors, status=status.HTTP_400_BAD_REQUEST)

                # handle other validation errors
                return Response(e.detail, status=status.HTTP_400_BAD_REQUEST)

            return Response(
                {"message": "Error creating account."},
                status=status.HTTP_400_BAD_REQUEST,
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
        try:
            # Make request data mutable and add user ID
            mutable_data = request.data.copy()
            mutable_data["user"] = self.request.user.id

            # Create serializer with mutable data
            serializer = self.get_serializer(data=mutable_data)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)

            headers = self.get_success_headers(serializer.data)
            return Response(
                serializer.data, status=status.HTTP_201_CREATED, headers=headers
            )

        except Exception as e:
            logger.info(f"Error creating profile: {str(e)}")
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


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class VerifyEmailView(generics.CreateAPIView):
    """Verify a user's email address using a verification token."""

    serializer_class = VerifyEmailTokenSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = VerifyEmailToken.objects.all()

    def create(self, request, *args, **kwargs):
        user = self.request.user
        user_token = getattr(user, "verify_email_token", None)
        request_token = request.data.get("token")

        if not request_token:
            return Response(
                {"error": "Verification token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user.is_email_verified:
            return Response(
                {"error": "Email already verified"}, status=status.HTTP_400_BAD_REQUEST
            )

        if not user_token:
            return Response(
                {"error": "No verification token found"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if user_token.token != request_token:
            return Response(
                {"error": "Invalid verification code"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if timezone.now() - user_token.created_at > timedelta(minutes=10):
            return Response(
                {"error": "Verification code has expired"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                user.is_email_verified = True
                user.save()
                user_token.delete()
        except Exception as e:
            logger.error(f"Error verifying email for user {user.id}: {str(e)}")
            return Response(
                {"error": "Failed to verify email"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(
            {"message": "Email successfully verified"}, status=status.HTTP_200_OK
        )


@extend_schema_view(
    post=extend_schema(parameters=[auth_profile_param]),
)
class RequestNewVerifyEmailTokenView(generics.CreateAPIView):
    serializer_class = VerifyEmailTokenSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = VerifyEmailToken.objects.all()

    def post(self, request, *args, **kwargs):
        user = self.request.user
        logger.info(f"Verification token requested for user {user.email}")

        if user.is_email_verified:
            logger.warning(f"Already verified user {user.email} requested new token")
            return Response(
                {"error": "Email already verified"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            with transaction.atomic():
                # Delete old token if exists
                VerifyEmailToken.objects.filter(user=user).delete()

                # Create new token
                token = generate_verification_code()
                serializer = self.get_serializer(data={"user": user.id, "token": token})
                serializer.is_valid(raise_exception=True)
                serializer.save()

                # Send verification email
                send_verification_email(user, token)

            logger.info(f"Verification token sent successfully to {user.email}")
            return Response(
                {"message": "Verification token sent."}, status=status.HTTP_201_CREATED
            )

        except Exception as e:
            logger.error(f"Error sending verification token to {user.email}: {str(e)}")
            return Response(
                {"error": "Failed to send verification token."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class CreateResetPasswordTokenView(generics.CreateAPIView):
    """Create a reset password token and send it via email."""

    serializer_class = ResetPasswordTokenSerializer
    permission_classes = []  # Allow unauthenticated access
    authentication_classes = []
    queryset = ResetPasswordToken.objects.all()

    def create(self, request, *args, **kwargs):
        email = request.data.get("email")

        if not email:
            return Response(
                {"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST
            )

        # Find user with this email
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # Don't reveal if email exists or not for security
            return Response(
                {
                    "message": "If a user with this email exists, they will receive a reset code."
                },
                status=status.HTTP_200_OK,
            )

        try:
            with transaction.atomic():
                # Delete any existing reset tokens for this user
                ResetPasswordToken.objects.filter(user=user).delete()

                # Generate and save new token
                token = generate_verification_code()
                serializer = self.get_serializer(data={"user": user.id, "token": token})
                serializer.is_valid(raise_exception=True)
                serializer.save()

                # Send email with reset token
                send_reset_password_email(user, token)

            logger.info(f"Password reset token sent to {email}")
            return Response(
                {
                    "message": "If a user with this email exists, they will receive a reset code."
                },
                status=status.HTTP_200_OK,
            )

        except Exception as e:
            logger.error(f"Error creating reset token for {email}: {str(e)}")
            return Response(
                {"error": "Failed to process reset password request."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )


class ResetPasswordView(generics.CreateAPIView):
    """Reset user password using reset token."""

    permission_classes = []  # Allow unauthenticated access
    authentication_classes = []

    def create(self, request, *args, **kwargs):
        email = request.data.get("email")
        token = request.data.get("token")
        new_password = request.data.get("password")

        # Validate required fields
        if not all([email, token, new_password]):
            return Response(
                {"error": "Email, token and new password are required"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            # Find user and their reset token
            user = User.objects.get(email=email)
            reset_token = ResetPasswordToken.objects.get(user=user, token=token)

            # Check if token has expired (15 minutes)
            if timezone.now() - reset_token.created_at > timedelta(minutes=15):
                reset_token.delete()
                return Response(
                    {"error": "Reset token has expired"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            try:
                # Validate password using UserSerializer
                user_serializer = UserSerializer(
                    user, data={"password": new_password}, partial=True
                )
                try:
                    user_serializer.is_valid(raise_exception=True)
                except serializers.ValidationError as e:
                    if "password" in e.detail:
                        return Response(
                            {"error": e.detail["password"][0]},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                    raise e

                with transaction.atomic():
                    # Update password
                    user.set_password(new_password)
                    user.save()

                    # Delete the used token
                    reset_token.delete()

                logger.info(f"Password reset successful for {email}")
                return Response(
                    {"message": "Password reset successful"},
                    status=status.HTTP_200_OK,
                )

            except Exception as e:
                logger.error(f"Error resetting password for {email}: {str(e)}")
                return Response(
                    {"error": "Failed to reset password"},
                    status=status.HTTP_500_INTERNAL_SERVER_ERROR,
                )

        except User.DoesNotExist:
            # Don't reveal if email exists
            return Response(
                {"error": "Invalid confirmation code"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ResetPasswordToken.DoesNotExist:
            return Response(
                {"error": "Invalid confirmation code"},
                status=status.HTTP_400_BAD_REQUEST,
            )
