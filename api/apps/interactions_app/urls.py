"""
URL patterns for the interactions app.
"""

from django.urls import path
from . import views

app_name = "interactions_app"

urlpatterns = [
    # Likes
    path(
        "like/post/<int:pk>/",
        views.CreateDestroyLikeView.as_view(),
        name="like_post",
    ),
    
    # Comments
    path(
        "comment/post/<int:id>/",
        views.CreateCommentView.as_view(),
        name="create_comment",
    ),
    path(
        "comment/post/<int:pk>/list/",
        views.ListPostCommentsView.as_view(),
        name="list_post_comments",
    ),
    path(
        "comment/<int:pk>/replies/",
        views.ListCommentRepliesView.as_view(),
        name="list_comment_replies",
    ),
    path(
        "comment/<int:pk>/chain/",
        views.CommentChainRetrieveView.as_view(),
        name="comment_chain_retrieve",
    ),
    
    # Comment Likes
    path(
        "like/comment/<int:pk>/",
        views.CreateDestroyCommentLikeView.as_view(),
        name="like_comment",
    ),
    
    # Follows
    path(
        "follow/",
        views.CreateFollowView.as_view(),
        name="create_follow",
    ),
    path(
        "follow/<int:profile_id>/",
        views.DestroyFollowView.as_view(),
        name="destroy_follow",
    ),
    path(
        "followers/<int:id>/",
        views.ListFollowersView.as_view(),
        name="list_followers",
    ),
    path(
        "following/<int:id>/",
        views.ListFollowingView.as_view(),
        name="list_following",
    ),
    
    # Follow Requests
    path(
        "follow-requests/",
        views.ListFollowRequestsView.as_view(),
        name="list_follow_requests",
    ),
    path(
        "follow-requests/sent/",
        views.ListSentFollowRequestsView.as_view(),
        name="list_sent_follow_requests",
    ),
    path(
        "follow-request/<int:pk>/accept/",
        views.AcceptFollowRequestView.as_view(),
        name="accept_follow_request",
    ),
    path(
        "follow-request/<int:pk>/decline/",
        views.DeclineFollowRequestView.as_view(),
        name="decline_follow_request",
    ),
    path(
        "follow-request/<int:profile_id>/cancel/",
        views.CancelFollowRequestView.as_view(),
        name="cancel_follow_request",
    ),
]

