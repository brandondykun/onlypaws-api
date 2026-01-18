from django.urls import path
from . import views

app_name = "posts_app"

urlpatterns = [
    path("post/", views.CreatePostView.as_view(), name="create_post"),
    path(
        "post/<int:pk>/",
        views.RetrieveUpdateDestroyPostView.as_view(),
        name="retrieve_update_destroy_post",
    ),
    path(
        "post/<int:pk>/similar/",
        views.ListSimilarPostsView.as_view(),
        name="lists_similar_posts",
    ),
    path(
        "post/image/<int:pk>/",
        views.DestroyPostImageView.as_view(),
        name="destroy_post_image",
    ),
    path(
        "post/image/tag/",
        views.CreatePostImageTagView.as_view(),
        name="create_post_image_tag",
    ),
    path(
        "post/image/tag/<int:pk>/",
        views.DestroyPostImageTagView.as_view(),
        name="destroy_post_image_tag",
    ),
    path(
        "profile/<int:id>/tagged/",
        views.ListTaggedPostsView.as_view(),
        name="list_tagged_posts",
    ),
    path(
        "post/saved/",
        views.ListCreateSavedPostView.as_view(),
        name="list_create_saved_post",
    ),
    path(
        "post/saved/<int:post_id>/",
        views.DestroySavedPostView.as_view(),
        name="destroy_saved_post",
    ),
    # Profile posts and feeds
    path(
        "profile/<int:id>/posts/",
        views.ListProfilePostsView.as_view(),
        name="list_profile_posts",
    ),
    path(
        "post/feed/", views.RetrieveFeedView.as_view(), name="retrieve_feed"
    ),
    path(
        "post/explore/",
        views.ListExplorePostsView.as_view(),
        name="list_explore",
    ),
]
