from rest_framework import generics, permissions, status
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema_view, extend_schema

from core.schema_params import auth_profile_param
from .models import AppConfiguration
from .serializers import AdsConfigSerializer

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

