from django.urls import path
from . import views

app_name = 'config_app'

urlpatterns = [
    path('ads/', views.GetAdsConfigView.as_view(), name='ads-config'),
]

