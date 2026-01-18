from datetime import datetime

from rest_framework import generics, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema_view, extend_schema

from core.schema_params import auth_profile_param
from apps.core_app.middleware import get_maintenance_status
from .models import AppConfiguration
from .serializers import AdsConfigSerializer, SystemStatusSerializer


@extend_schema_view(
    get=extend_schema(parameters=[auth_profile_param]),
)
class GetAdsConfigView(generics.GenericAPIView):
    """
    Get the ads configuration.
    Returns enabled status and ad interval for displaying ads in the frontend.
    
    In the future, this can be enhanced to check user subscription status.
    """
    serializer_class = AdsConfigSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get(self, request, *args, **kwargs):
        try:
            config = AppConfiguration.objects.get(key='ads_config')
            serializer = AdsConfigSerializer(data=config.value)
            
            if serializer.is_valid():
                return Response(serializer.data, status=status.HTTP_200_OK)
            else:
                # If validation fails, return default values
                return Response({
                    'enabled': True,
                    'adInterval': 5
                }, status=status.HTTP_200_OK)
                
        except AppConfiguration.DoesNotExist:
            # Return default values if config doesn't exist
            return Response({
                'enabled': True,
                'adInterval': 5
            }, status=status.HTTP_200_OK)


@extend_schema_view(
    get=extend_schema(
        summary="Get system status",
        description="Returns the current operational status of the system. "
                    "This endpoint is publicly accessible and should always respond, "
                    "even during maintenance mode.",
        responses={200: SystemStatusSerializer},
    ),
)
class GetSystemStatusView(generics.GenericAPIView):
    """
    Get the current system status.
    
    Returns whether the system is operational or in maintenance mode.
    This endpoint is publicly accessible (no authentication required) and
    is designed to always respond, even when the system is in maintenance mode.
    """
    serializer_class = SystemStatusSerializer
    permission_classes = [permissions.AllowAny]
    
    def get(self, request, *args, **kwargs):
        # Use shared function to check maintenance status
        is_maintenance, message, end_time, _ = get_maintenance_status()
        
        # Parse end time if provided
        estimated_end_time = None
        if end_time:
            try:
                estimated_end_time = datetime.fromisoformat(end_time)
            except (ValueError, TypeError):
                pass
        
        response_data = {
            'status': 'maintenance' if is_maintenance else 'operational',
            'message': message if is_maintenance else None,
            'estimated_end_time': estimated_end_time,
        }
        
        serializer = self.get_serializer(data=response_data)
        serializer.is_valid(raise_exception=True)
        
        return Response(serializer.data, status=status.HTTP_200_OK)

