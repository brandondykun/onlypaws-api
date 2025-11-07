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
        views.RetrieveUpdateDestroyPostView.as_view(),
        name="retrieve_update_destroy_post",
    ),
    path(
        "post/<int:pk>/similar",
        views.ListSimilarPostsView.as_view(),
        name="lists_similar_posts",
    ),
    path(
        "post/image/<int:pk>/",
        views.DestroyPostImageView.as_view(),
        name="destroy_post_image",
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
        "comment/<int:pk>/chain/",
        views.CommentChainRetrieveView.as_view(),
        name="comment_chain_retrieve",
    ),
    # Profile posts and feeds
    path(
        "profile/<int:id>/posts/",
        views.ListProfilePostsView.as_view(),
        name="list_profile_posts",
    ),
    path(
        "profile/<int:id>/feed/", views.RetrieveFeedView.as_view(), name="retrieve_feed"
    ),
    path(
        "profile/<int:id>/explore/",
        views.ListExplorePostsView.as_view(),
        name="list_explore",
    ),
    path("", include(router.urls)),
]
