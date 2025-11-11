"""
Test utilities for notifications app.
"""

from django.urls import reverse


NOTIFICATIONS_LIST_URL = reverse("notifications_app:list_notifications")
NOTIFICATIONS_UNREAD_LIST_URL = reverse("notifications_app:list_unread_notifications")
NOTIFICATIONS_MARK_ALL_READ_URL = reverse("notifications_app:mark_all_notifications_read")
NOTIFICATIONS_GET_COUNTS_URL = reverse("notifications_app:get_notification_counts")


def retrieve_update_notification_url(notification_id: int):
    """Create and return a retrieve update notification url.

    Parameters
    ----------
    notification_id : int
        The id of the Notification to retrieve or update.
    """
    return reverse("notifications_app:retrieve_update_notification", args=[notification_id])