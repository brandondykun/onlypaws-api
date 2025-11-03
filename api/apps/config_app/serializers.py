from rest_framework import serializers
from .models import AppConfiguration


class AppConfigurationSerializer(serializers.ModelSerializer):
    """Serializer for AppConfiguration model."""
    
    class Meta:
        model = AppConfiguration
        fields = ['key', 'value', 'description', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']


class AdsConfigSerializer(serializers.Serializer):
    """Serializer for ads configuration response."""
    enabled = serializers.BooleanField()
    adInterval = serializers.IntegerField()

