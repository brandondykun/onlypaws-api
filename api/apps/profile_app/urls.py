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
    path(
        "<int:pk>/",
        views.RetrieveUpdateDestroyProfileView.as_view(),
        name="retrieve_update_destroy_profile",
    ),
    
    # Profile Images
    path(
        "image/",
        views.CreateProfileImageView.as_view(),
        name="create_profile_image",
    ),
    path(
        "image/<int:pk>/",
        views.UpdateProfileImageView.as_view(),
        name="update_profile_image",
    ),
    
    # Pet Types
    path(
        "pet-types/",
        views.ListPetTypesView.as_view(),
        name="list_pet_types",
    ),
    
    # Profile Search
    path(
        "search/",
        views.ListSearchedProfilesView.as_view(),
        name="search_profiles",
    ),
]

