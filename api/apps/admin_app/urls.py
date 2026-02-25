"""
URL configuration for admin dashboard app.
"""

from django.urls import path
from .views import (
    AdminDashboardStatsView,
    AdminUserListView,
    AdminUserDetailView,
    AdminProfileListView,
    AdminProfileDetailView,
    AdminAnnouncementListView,
    AdminAnnouncementDetailView,
    AdminReportReasonListView,
    AdminReportReasonDetailView,
    AdminProfanityLogListView,
    AdminProfanityLogDetailView,
)

urlpatterns = [
    path("stats/", AdminDashboardStatsView.as_view(), name="admin-dashboard-stats"),
    path("users/", AdminUserListView.as_view(), name="admin-user-list"),
    path("users/<int:pk>/", AdminUserDetailView.as_view(), name="admin-user-detail"),
    path("profiles/", AdminProfileListView.as_view(), name="admin-profile-list"),
    path("profiles/<int:pk>/", AdminProfileDetailView.as_view(), name="admin-profile-detail"),
    path("announcements/", AdminAnnouncementListView.as_view(), name="admin-announcement-list"),
    path("announcements/<int:pk>/", AdminAnnouncementDetailView.as_view(), name="admin-announcement-detail"),
    path("report-reasons/", AdminReportReasonListView.as_view(), name="admin-report-reason-list"),
    path("report-reasons/<int:pk>/", AdminReportReasonDetailView.as_view(), name="admin-report-reason-detail"),
    path("profanity-logs/", AdminProfanityLogListView.as_view(), name="admin-profanity-log-list"),
    path("profanity-logs/<int:pk>/", AdminProfanityLogDetailView.as_view(), name="admin-profanity-log-detail"),
]

