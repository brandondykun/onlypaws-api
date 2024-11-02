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
    path("post/like/", views.CreateDestroyLikeView.as_view(), name="create_like"),
    path(
        "post/like/<int:pk>", views.CreateDestroyLikeView.as_view(), name="destroy_like"
    ),
    path("follow/", views.CreateDestroyFollowView.as_view(), name="create_follow"),
    path(
        "follow/<int:pk>/<int:auth_profile_id>/",
        views.CreateDestroyFollowView.as_view(),
        name="destroy_follow",
    ),
    # TODO this should be changed to post/ or profile/post??
    path(
        "profile/posts/",
        views.ListProfilePostsView.as_view(),
        name="list_profile_posts",
    ),
    path(
        "profile/<int:pk>",
        views.RetrieveProfileView.as_view(),
        name="retrieve_profile",
    ),
    path("feed/", views.RetrieveFeedView.as_view(), name="retrieve_feed"),
    path("post/comment/", views.CreateCommentView.as_view(), name="create_comment"),
    path(
        "post/<int:pk>/comments/",
        views.ListPostCommentsView.as_view(),
        name="list_post_comments",
    ),
    path(
        "profile/search",
        views.ListSearchedProfilesView.as_view(),
        name="search_profiles",
    ),
    path(
        "explore/",
        views.ListExplorePostsView.as_view(),
        name="list_explore",
    ),
]
