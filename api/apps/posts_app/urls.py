from django.urls import path
from . import views

app_name = "posts_app"

urlpatterns = [
    path("post/", views.CreatePostView.as_view(), name="create_post"),
    path(
        "post/<int:pk>",
        views.RetrievePostView.as_view(),
        name="retrieve_post",
    ),
    path(
        "post/<int:pk>/similar",
        views.ListSimilarPostsView.as_view(),
        name="lists_similar_posts",
    ),
    path(
        "post/<int:post_id>/like/", views.CreateLikeView.as_view(), name="create_like"
    ),
    path(
        "post/<int:pk>/like/<int:profile_id>",
        views.DestroyLikeView.as_view(),
        name="destroy_like",
    ),
    path("post/comment/", views.CreateCommentView.as_view(), name="create_comment"),
    path(
        "post/<int:pk>/comments/",
        views.ListPostCommentsView.as_view(),
        name="list_post_comments",
    ),
    path(
        "profile/<int:id>/follow/",
        views.CreateFollowView.as_view(),
        name="create_follow",
    ),
    path(
        "profile/<int:auth_profile_id>/follow/<int:pk>/",
        views.DestroyFollowView.as_view(),
        name="destroy_follow",
    ),
    # TODO this should be changed to post/ or profile/post??
    path(
        "profile/<int:id>/posts/",
        views.ListProfilePostsView.as_view(),
        name="list_profile_posts",
    ),
    path(
        "profile/<int:pk>",
        views.RetrieveProfileView.as_view(),
        name="retrieve_profile",
    ),
    path(
        "profile/<int:id>/feed/", views.RetrieveFeedView.as_view(), name="retrieve_feed"
    ),
    path(
        "profile/<int:id>/search",
        views.ListSearchedProfilesView.as_view(),
        name="search_profiles",
    ),
    path(
        "profile/<int:id>/explore/",
        views.ListExplorePostsView.as_view(),
        name="list_explore",
    ),
]
