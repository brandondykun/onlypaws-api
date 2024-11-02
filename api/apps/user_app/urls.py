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
        views.SearchCreateProfileView.as_view(),
        name="search_create_profile",
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
        views.CreateUpdateProfileImageView.as_view(),
        name="create_update_profile_image",
    ),
    path(
        "profile-image/<int:pk>/",
        views.CreateUpdateProfileImageView.as_view(),
        name="update_profile_image",
    ),
]
