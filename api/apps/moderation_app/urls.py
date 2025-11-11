"""
URL configuration for moderation app.
"""
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ReportReasonViewSet, PostReportViewSet

app_name = "moderation_app"

router = DefaultRouter()
router.register(r"report-reason", ReportReasonViewSet, basename="report-reason")
router.register(r"report", PostReportViewSet, basename="report")

urlpatterns = [
    path("", include(router.urls)),
]

