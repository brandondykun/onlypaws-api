from rest_framework import serializers
from .models import Announcement


class AnnouncementSerializer(serializers.ModelSerializer):
    """Serializer for Announcement model."""
    
    class Meta:
        model = Announcement
        fields = ['id', 'title', 'message', 'priority', 'announcement_type', 'created_at']
        read_only_fields = ['id', 'created_at']

