"""
URL configuration for moderation app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    ReportReasonViewSet,
    PostReportViewSet,
    ProfileReportReasonViewSet,
    ProfileReportViewSet,
    CheckTextView,
    BlockProfileView,
    UnblockProfileView,
    ListBlockedProfilesView,
)

app_name = "moderation_app"

router = DefaultRouter()
router.register(r"report-reason", ReportReasonViewSet, basename="report-reason")
router.register(r"report", PostReportViewSet, basename="report")
router.register(r"profile-report-reason", ProfileReportReasonViewSet, basename="profile-report-reason")
router.register(r"profile-report", ProfileReportViewSet, basename="profile-report")

urlpatterns = [
    path("", include(router.urls)),
    path("check-text/", CheckTextView.as_view(), name="check-text"),
    path("block/", BlockProfileView.as_view(), name="block-profile"),
    path("block/list/", ListBlockedProfilesView.as_view(), name="list-blocked-profiles"),
    path("block/<str:public_id>/", UnblockProfileView.as_view(), name="unblock-profile"),
]

