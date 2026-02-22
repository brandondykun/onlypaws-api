from django.urls import path
from . import views
from .authentication import (
    AppleAuthView,
    CustomTokenObtainPairView,
    CustomTokenRefreshView,
    GoogleAuthView,
    LogoutView,
    LogoutAllView,
)

app_name = "user_app"

urlpatterns = [
    path("create-user/", views.CreateUserView.as_view(), name="create_user"),
    path(
        "users/<int:pk>/",
        views.RetrieveUpdateUserView.as_view(),
        name="retrieve_update_user",
    ),
    # JWT Authentication endpoints with dual-client support (web + mobile)
    # See authentication.py for detailed documentation on client-type behavior
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("google-auth/", GoogleAuthView.as_view(), name="google_auth"),
    path("apple-auth/", AppleAuthView.as_view(), name="apple_auth"),
    path("refresh/", CustomTokenRefreshView.as_view(), name="token_refresh"),
    path("logout/", LogoutView.as_view(), name="logout"),
    path("logout-all/", LogoutAllView.as_view(), name="logout_all"),
    path("my-info/", views.RetrieveUserInfoView.as_view(), name="my_info"),
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
    path(
        "request-email-change/",
        views.RequestEmailChangeView.as_view(),
        name="request-email-change",
    ),
    path(
        "verify-email-change/",
        views.VerifyEmailChangeView.as_view(),
        name="verify-email-change",
    ),
    path(
        "complete-onboarding/",
        views.CompleteOnboardingView.as_view(),
        name="complete-onboarding",
    ),
]
