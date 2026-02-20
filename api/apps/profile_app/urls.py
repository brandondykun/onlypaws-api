from django.urls import path
from . import views

app_name = "profile_app"

urlpatterns = [
    # Profile CRUD
    path(
        "",
        views.CreateProfileView.as_view(),
        name="create_profile",
    ),
    # Literal paths before <str:public_id> so "search", "image", "pet-types" are not captured
    path(
        "search/",
        views.ListSearchedProfilesView.as_view(),
        name="search_profiles",
    ),
    path(
        "pet-types/",
        views.ListPetTypesView.as_view(),
        name="list_pet_types",
    ),
    path(
        "image/",
        views.CreateProfileImageView.as_view(),
        name="create_profile_image",
    ),
    path(
        "image/upload-url/",
        views.ProfileImageUploadUrlView.as_view(),
        name="profile_image_upload_url",
    ),
    path(
        "image/confirm-upload/",
        views.ConfirmProfileImageUploadView.as_view(),
        name="confirm_profile_image_upload",
    ),
    path(
        "image/<str:public_id>/",
        views.UpdateProfileImageView.as_view(),
        name="update_profile_image",
    ),
    path(
        "<str:public_id>/",
        views.RetrieveUpdateDestroyProfileView.as_view(),
        name="retrieve_update_destroy_profile",
    ),
]

