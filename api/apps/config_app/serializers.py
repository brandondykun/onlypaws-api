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


class SystemStatusSerializer(serializers.Serializer):
    """Serializer for system status response."""
    status = serializers.ChoiceField(choices=['operational', 'maintenance'])
    message = serializers.CharField(allow_null=True, allow_blank=True, required=False)
    estimated_end_time = serializers.DateTimeField(allow_null=True, required=False)

