from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import FeedbackViewSet, FeedbackCommentViewSet

app_name = "feedback_app"

# Create a router and register our viewsets with it
router = DefaultRouter()
router.register(r"feedback", FeedbackViewSet, basename="feedback")
router.register(
    r"feedback-comments", FeedbackCommentViewSet, basename="feedback-comments"
)

# The API URLs are now determined automatically by the router
urlpatterns = [
    path("", include(router.urls)),
]
