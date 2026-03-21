"""
URL configuration for admin dashboard app.
"""

from django.urls import path
from .views import AdminUserGrowthView, AdminPostGrowthView

urlpatterns = [
    path(
        "charts/user-growth/", AdminUserGrowthView.as_view(), name="admin-user-growth"
    ),
    path(
        "charts/post-growth/", AdminPostGrowthView.as_view(), name="admin-post-growth"
    ),
]
