from django.urls import path, include
from . import views
from rest_framework.routers import DefaultRouter
from .views import ReportReasonViewSet, PostReportViewSet

app_name = "posts_app"

router = DefaultRouter()
router.register(r"report-reason", ReportReasonViewSet, basename="report-reason")
router.register(r"report", PostReportViewSet, basename="report")


urlpatterns = [
    path("post/", views.CreatePostView.as_view(), name="create_post"),
    path(
        "post/<int:pk>",
        views.RetrieveDestroyPostView.as_view(),
        name="retrieve_destroy_post",
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
    path(
        "post/<int:id>/comment/",
        views.CreateCommentView.as_view(),
        name="create_comment",
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
    path(
        "comment/<int:comment_id>/like/",
        views.CreateCommentLikeView.as_view(),
        name="create_comment_like",
    ),
    path(
        "comment/<int:comment_id>/like/<int:profile_id>/",
        views.DestroyCommentLikeView.as_view(),
        name="destroy_comment_like",
    ),
    path(
        "post/<int:pk>/comments/",
        views.ListPostCommentsView.as_view(),
        name="list_post_comments",
    ),
    path(
        "post/<int:pk>/comments/<int:comment_id>/reply/",
        views.ListCommentRepliesView.as_view(),
        name="list_comment_replies",
    ),
    path(
        "profile/<int:id>/follow/",
        views.CreateFollowView.as_view(),
        name="create_follow",
    ),
    path(
        "profile/<int:id>/followers/",
        views.ListFollowersView.as_view(),
        name="list_followers",
    ),
    path(
        "profile/<int:id>/following/",
        views.ListFollowingView.as_view(),
        name="list_following",
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
    path("", include(router.urls)),
]
