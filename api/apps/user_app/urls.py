from django.urls import path
from . import views

from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
)

app_name = "user_app"

urlpatterns = [
    path("create-user/", views.CreateUserView.as_view(), name="create_user"),
    path(
        "users/<int:pk>/",
        views.RetrieveUpdateUserView.as_view(),
        name="retrieve_update_user",
    ),
    path(
        "profile/",
        views.CreateProfileView.as_view(),
        name="create_profile",
    ),
    path(
        "profile/<int:pk>/",
        views.RetrieveUpdateProfileView.as_view(),
        name="retrieve_update_profile",
    ),
    path("login/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("my-info/", views.RetrieveUserInfoView.as_view(), name="my_info"),
    path(
        "profile-image/",
        views.CreateProfileImageView.as_view(),
        name="create_profile_image",
    ),
    path(
        "profile-image/<int:pk>/",
        views.UpdateProfileImageView.as_view(),
        name="update_profile_image",
    ),
    path(
        "pet-type-options/",
        views.ListPetTypesView.as_view(),
        name="list_pet_types",
    ),
    path(
        "verify-email-token/",
        views.VerifyEmailView.as_view(),
        name="verify_email_token",
    ),
    path(
        "resend-verify-email-token/",
        views.RequestNewVerifyEmailTokenView.as_view(),
        name="request_new_verify_email_token",
    ),
    path(
        "request-password-reset/",
        views.CreateResetPasswordTokenView.as_view(),
        name="request_password_reset",
    ),
    path(
        "reset-password/",
        views.ResetPasswordView.as_view(),
        name="reset_password",
    ),
    path(
        "change-password/", views.ChangePasswordView.as_view(), name="change_password"
    ),
]
