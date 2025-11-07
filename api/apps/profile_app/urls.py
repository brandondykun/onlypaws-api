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
        views.UpdateDestroyProfileView.as_view(),
        name="update_destroy_profile",
    ),
    path(
        "<int:pk>/detail/",
        views.RetrieveProfileView.as_view(),
        name="retrieve_profile",
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
        "<int:id>/search/",
        views.ListSearchedProfilesView.as_view(),
        name="search_profiles",
    ),
    
    # Follows
    path(
        "<int:id>/follow/",
        views.CreateFollowView.as_view(),
        name="create_follow",
    ),
    path(
        "<int:id>/followers/",
        views.ListFollowersView.as_view(),
        name="list_followers",
    ),
    path(
        "<int:id>/following/",
        views.ListFollowingView.as_view(),
        name="list_following",
    ),
    path(
        "<int:auth_profile_id>/follow/<int:pk>/",
        views.DestroyFollowView.as_view(),
        name="destroy_follow",
    ),
]

