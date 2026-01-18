from django.urls import path
from . import views

app_name = 'announcements_app'

urlpatterns = [
    path('announcements/', views.AnnouncementListView.as_view(), name='announcement-list'),
]

