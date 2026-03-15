from django.urls import path

from .views import CurrentTermsView, AcceptTermsView

app_name = "legal_app"

urlpatterns = [
    path("terms/current/", CurrentTermsView.as_view(), name="current-terms"),
    path("terms/accept/", AcceptTermsView.as_view(), name="accept-terms"),
]
