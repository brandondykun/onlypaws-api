from django.urls import path
from . import views

app_name = "notifications_app"

urlpatterns = [
    path(
        "notifications/",
        views.ListNotificationsView.as_view(),
        name="list_notifications"
    ),
    path(
        "notifications/unread/",
        views.ListUnreadNotificationsView.as_view(),
        name="list_unread_notifications"
    ),
    path(
        "notifications/<int:pk>/",
        views.RetrieveUpdateNotificationView.as_view(),
        name="retrieve_update_notification"
    ),
    path(
        "notifications/mark-all-read/",
        views.mark_all_notifications_read,
        name="mark_all_notifications_read"
    ),
    path(
        "notifications/counts/",
        views.get_notification_counts,
        name="get_notification_counts"
    ),
]
