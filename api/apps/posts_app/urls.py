from django.urls import path
from . import views

app_name = "posts_app"

urlpatterns = [
    path("post/", views.CreatePostView.as_view(), name="create_post"),
    path("post/prepare-upload/", views.PrepareUploadView.as_view(), name="prepare_upload"),
    path(
        "post/saved/",
        views.ListCreateSavedPostView.as_view(),
        name="list_create_saved_post",
    ),
    path(
        "post/saved/<str:post_public_id>/",
        views.DestroySavedPostView.as_view(),
        name="destroy_saved_post",
    ),
    path(
        "post/feed/", views.RetrieveFeedView.as_view(), name="retrieve_feed"
    ),
    path(
        "post/explore/",
        views.ListExplorePostsView.as_view(),
        name="list_explore",
    ),
    path(
        "post/<str:public_id>/",
        views.RetrieveUpdateDestroyPostView.as_view(),
        name="retrieve_update_destroy_post",
    ),
    path(
        "post/<str:public_id>/similar/",
        views.ListSimilarPostsView.as_view(),
        name="lists_similar_posts",
    ),
    path(
        "post/image/<str:public_id>/",
        views.DestroyPostImageView.as_view(),
        name="destroy_post_image",
    ),
    path(
        "post/image/tag/",
        views.CreatePostImageTagView.as_view(),
        name="create_post_image_tag",
    ),
    path(
        "post/image/tag/<str:public_id>/",
        views.DestroyPostImageTagView.as_view(),
        name="destroy_post_image_tag",
    ),
    path(
        "profile/<str:public_id>/tagged/",
        views.ListTaggedPostsView.as_view(),
        name="list_tagged_posts",
    ),
    path(
        "profile/<str:public_id>/posts/",
        views.ListProfilePostsView.as_view(),
        name="list_profile_posts",
    ),
]
