"""
URL configuration for admin dashboard app.
"""

from django.urls import path
from .views import AdminUserGrowthView

urlpatterns = [
    path(
        "charts/user-growth/", AdminUserGrowthView.as_view(), name="admin-user-growth"
    ),
]
