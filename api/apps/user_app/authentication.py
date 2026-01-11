"""
Custom JWT Authentication Views for Dual-Client Support (Mobile + Web)

This module provides custom token views that handle authentication differently
based on the client type (mobile app vs web frontend).

Client Type Detection:
    - Uses the 'X-Client-Type' header to determine client type
    - Valid values: 'web' or 'mobile' (case-insensitive)
    - Missing header defaults to 'mobile' for backward compatibility

Mobile Clients:
    - Receive both access and refresh tokens in the response body
    - This maintains backward compatibility with existing mobile app behavior

Web Clients:
    - Receive only the access token in the response body
    - Refresh token is set as an HttpOnly, Secure cookie with SameSite=Strict
    - This provides better security for browser-based applications
    - Prevents XSS attacks from accessing the refresh token

Token Rotation:
    - Both client types benefit from token rotation (new refresh token on each refresh)
    - Old tokens are blacklisted after rotation

Usage:
    Mobile client login request:
        POST /api/v1/auth/login/
        Headers: X-Client-Type: mobile (or omit header)
        Body: {"email": "...", "password": "..."}
        Response: {"access": "...", "refresh": "..."}

    Web client login request:
        POST /api/v1/auth/login/
        Headers: X-Client-Type: web
        Body: {"email": "...", "password": "..."}
        Response: {"access": "..."}
        Cookie: refresh_token=... (HttpOnly, Secure, SameSite=Strict)
"""

import logging
from django.conf import settings
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from drf_spectacular.utils import extend_schema, OpenApiParameter, OpenApiExample
from drf_spectacular.types import OpenApiTypes

logger = logging.getLogger(__name__)


# Constants for client types
CLIENT_TYPE_WEB = "web"
CLIENT_TYPE_MOBILE = "mobile"
CLIENT_TYPE_HEADER = "X-Client-Type"


def get_client_type(request) -> str:
    """
    Determine the client type from the request headers.
    
    Args:
        request: The HTTP request object
        
    Returns:
        str: Either 'web' or 'mobile' (defaults to 'mobile' if header is missing)
    """
    client_type = request.headers.get(CLIENT_TYPE_HEADER, CLIENT_TYPE_MOBILE).lower()
    if client_type not in (CLIENT_TYPE_WEB, CLIENT_TYPE_MOBILE):
        logger.warning(f"Invalid client type '{client_type}', defaulting to mobile")
        return CLIENT_TYPE_MOBILE
    return client_type


def get_cookie_settings() -> dict:
    """
    Get the cookie settings from Django settings.
    
    Returns:
        dict: Cookie configuration settings
    """
    simple_jwt = getattr(settings, "SIMPLE_JWT", {})
    return {
        "key": simple_jwt.get("AUTH_COOKIE", "refresh_token"),
        "domain": simple_jwt.get("AUTH_COOKIE_DOMAIN", None),
        "secure": simple_jwt.get("AUTH_COOKIE_SECURE", True),
        "httponly": simple_jwt.get("AUTH_COOKIE_HTTP_ONLY", True),
        "path": simple_jwt.get("AUTH_COOKIE_PATH", "/"),
        "samesite": simple_jwt.get("AUTH_COOKIE_SAMESITE", "Strict"),
    }


def set_refresh_token_cookie(response: Response, refresh_token: str) -> Response:
    """
    Set the refresh token as an HttpOnly cookie on the response.
    
    Args:
        response: The DRF Response object
        refresh_token: The refresh token string
        
    Returns:
        Response: The modified response with the cookie set
    """
    cookie_settings = get_cookie_settings()
    simple_jwt = getattr(settings, "SIMPLE_JWT", {})
    
    # Get the refresh token lifetime for max_age
    from datetime import timedelta
    refresh_lifetime = simple_jwt.get("REFRESH_TOKEN_LIFETIME", timedelta(days=7))
    max_age = int(refresh_lifetime.total_seconds())
    
    response.set_cookie(
        key=cookie_settings["key"],
        value=refresh_token,
        max_age=max_age,
        domain=cookie_settings["domain"],
        secure=cookie_settings["secure"],
        httponly=cookie_settings["httponly"],
        path=cookie_settings["path"],
        samesite=cookie_settings["samesite"],
    )
    
    return response


def delete_refresh_token_cookie(response: Response) -> Response:
    """
    Delete the refresh token cookie from the response.
    
    Args:
        response: The DRF Response object
        
    Returns:
        Response: The modified response with the cookie deleted
    """
    cookie_settings = get_cookie_settings()
    
    response.delete_cookie(
        key=cookie_settings["key"],
        domain=cookie_settings["domain"],
        path=cookie_settings["path"],
        samesite=cookie_settings["samesite"],
    )
    
    return response


@extend_schema(
    tags=["Authentication"],
    summary="Obtain JWT token pair (login)",
    description="""
    Authenticate a user and return JWT tokens.
    
    Client Type Behavior:
    - Mobile (X-Client-Type: mobile or header omitted): Returns both access and refresh tokens in response body
    - Web (X-Client-Type: web): Returns access token in body, refresh token as HttpOnly cookie
    
    This endpoint supports both mobile apps and web frontends with appropriate security for each.
    """,
    parameters=[
        OpenApiParameter(
            name="X-Client-Type",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.HEADER,
            required=False,
            description="Client type: 'web' or 'mobile'. Defaults to 'mobile' if omitted.",
            examples=[
                OpenApiExample("Web Client", value="web"),
                OpenApiExample("Mobile Client", value="mobile"),
            ],
        ),
    ],
)
class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom token obtain view that handles web and mobile clients differently.
    
    Mobile clients receive both tokens in the response body.
    Web clients receive the access token in body and refresh token as HttpOnly cookie.
    """
    
    def post(self, request, *args, **kwargs):
        # Get the standard response from parent class
        response = super().post(request, *args, **kwargs)
        
        if response.status_code == status.HTTP_200_OK:
            client_type = get_client_type(request)
            refresh_token = response.data.get("refresh")
            
            if client_type == CLIENT_TYPE_WEB and refresh_token:
                # For web clients: set refresh token as cookie and remove from body
                set_refresh_token_cookie(response, refresh_token)
                del response.data["refresh"]
                logger.info(f"Web client login: refresh token set as cookie")
            else:
                # For mobile clients: keep both tokens in body (default behavior)
                logger.info(f"Mobile client login: both tokens in response body")
        
        return response


@extend_schema(
    tags=["Authentication"],
    summary="Refresh JWT access token",
    description="""
    Refresh the access token using a valid refresh token.
    
    Client Type Behavior:
    - Mobile (X-Client-Type: mobile or header omitted): 
      - Send refresh token in request body
      - Receive new access token and new refresh token in response body
    - Web (X-Client-Type: web):
      - Browser automatically sends refresh token via cookie
      - Receive only new access token in response body
      - New refresh token automatically set as updated cookie
    
    Token rotation is enabled: each refresh generates a new refresh token and blacklists the old one.
    """,
    parameters=[
        OpenApiParameter(
            name="X-Client-Type",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.HEADER,
            required=False,
            description="Client type: 'web' or 'mobile'. Defaults to 'mobile' if omitted.",
        ),
    ],
)
class CustomTokenRefreshView(TokenRefreshView):
    """
    Custom token refresh view that handles web and mobile clients differently.
    
    Mobile clients send refresh token in body and receive new tokens in body.
    Web clients send refresh token via cookie and receive only access token in body,
    with the new refresh token set as an updated cookie.
    """
    
    def get_refresh_token(self, request) -> str | None:
        """
        Get the refresh token from request body or cookie.
        
        For web clients, checks the HttpOnly cookie if not in body.
        For mobile clients, only checks the request body.
        """
        # First check request body
        refresh_token = request.data.get("refresh")
        if refresh_token:
            logger.debug("Refresh token found in request body")
            return refresh_token
        
        # For web clients, fall back to cookie
        client_type = get_client_type(request)
        if client_type == CLIENT_TYPE_WEB:
            cookie_name = get_cookie_settings()["key"]
            refresh_token = request.COOKIES.get(cookie_name)
            if refresh_token:
                logger.debug("Web client refresh: using token from cookie")
                return refresh_token
            else:
                # Log available cookies for debugging (without values for security)
                available_cookies = list(request.COOKIES.keys())
                logger.debug(f"No refresh cookie found. Cookie name expected: '{cookie_name}'. Cookies received: {available_cookies}")
        
        return None
    
    def post(self, request, *args, **kwargs):
        client_type = get_client_type(request)
        
        # Get refresh token from body or cookie
        refresh_token = self.get_refresh_token(request)
        
        if not refresh_token:
            logger.warning(f"Token refresh failed: no refresh token provided (client_type={client_type})")
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        # Create serializer with the refresh token directly
        serializer = self.get_serializer(data={"refresh": refresh_token})
        
        try:
            serializer.is_valid(raise_exception=True)
        except TokenError as e:
            logger.warning(f"Token refresh failed: {str(e)}")
            raise InvalidToken(e.args[0])
        
        # Build successful response
        response = Response(serializer.validated_data, status=status.HTTP_200_OK)
        new_refresh_token = serializer.validated_data.get("refresh")
        
        if client_type == CLIENT_TYPE_WEB and new_refresh_token:
            # For web clients: set new refresh token as cookie and remove from body
            set_refresh_token_cookie(response, new_refresh_token)
            del response.data["refresh"]
            logger.debug("Web client refresh: new refresh token set as cookie")
        else:
            # For mobile clients: keep both tokens in body (default behavior)
            logger.debug("Mobile client refresh: both tokens in response body")
        
        return response


@extend_schema(
    tags=["Authentication"],
    summary="Logout and invalidate refresh token",
    description="""
    Logout the user by blacklisting their refresh token.
    
    Client Type Behavior:
    - Mobile (X-Client-Type: mobile or header omitted): Send refresh token in request body
    - Web (X-Client-Type: web): Browser sends refresh token via cookie (no body needed)
    
    The refresh token will be blacklisted and cannot be used again.
    For web clients, the refresh cookie will also be deleted.
    """,
    parameters=[
        OpenApiParameter(
            name="X-Client-Type",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.HEADER,
            required=False,
            description="Client type: 'web' or 'mobile'. Defaults to 'mobile' if omitted.",
        ),
    ],
)
class LogoutView(APIView):
    """
    Logout view that blacklists the refresh token.
    
    Handles both mobile (token in body) and web (token in cookie) clients.
    Always deletes the refresh cookie for web clients.
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        client_type = get_client_type(request)
        refresh_token = None
        
        # Try to get refresh token from body first
        refresh_token = request.data.get("refresh")
        
        # For web clients, fall back to cookie if not in body
        if not refresh_token and client_type == CLIENT_TYPE_WEB:
            cookie_name = get_cookie_settings()["key"]
            refresh_token = request.COOKIES.get(cookie_name)
        
        if not refresh_token:
            return Response(
                {"error": "Refresh token is required"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        
        try:
            # Blacklist the refresh token
            token = RefreshToken(refresh_token)
            token.blacklist()
            
            logger.info(f"User {request.user.email} logged out successfully")
            
            # Create response
            response = Response(
                {"message": "Successfully logged out"},
                status=status.HTTP_200_OK,
            )
            
            # For web clients, also delete the cookie
            if client_type == CLIENT_TYPE_WEB:
                delete_refresh_token_cookie(response)
                logger.debug("Web client logout: refresh cookie deleted")
            
            return response
            
        except TokenError as e:
            logger.warning(f"Logout failed - invalid token: {str(e)}")
            
            # Even if token is invalid, delete the cookie for web clients
            response = Response(
                {"error": "Invalid or expired token"},
                status=status.HTTP_400_BAD_REQUEST,
            )
            
            if client_type == CLIENT_TYPE_WEB:
                delete_refresh_token_cookie(response)
            
            return response


@extend_schema(
    tags=["Authentication"],
    summary="Logout from all devices",
    description="""
    Logout the user from all devices by blacklisting all their outstanding refresh tokens.
    
    This will invalidate all active sessions for the authenticated user.
    For web clients, the current refresh cookie will also be deleted.
    """,
    parameters=[
        OpenApiParameter(
            name="X-Client-Type",
            type=OpenApiTypes.STR,
            location=OpenApiParameter.HEADER,
            required=False,
            description="Client type: 'web' or 'mobile'. Defaults to 'mobile' if omitted.",
        ),
    ],
)
class LogoutAllView(APIView):
    """
    Logout from all devices by blacklisting all outstanding tokens for the user.
    """
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, *args, **kwargs):
        client_type = get_client_type(request)
        user = request.user
        
        try:
            # Get all outstanding tokens for this user and blacklist them
            outstanding_tokens = OutstandingToken.objects.filter(user=user)
            blacklisted_count = 0
            
            for outstanding_token in outstanding_tokens:
                # Check if not already blacklisted
                if not BlacklistedToken.objects.filter(token=outstanding_token).exists():
                    BlacklistedToken.objects.create(token=outstanding_token)
                    blacklisted_count += 1
            
            logger.info(
                f"User {user.email} logged out from all devices. "
                f"Blacklisted {blacklisted_count} tokens."
            )
            
            # Create response
            response = Response(
                {
                    "message": "Successfully logged out from all devices",
                    "sessions_terminated": blacklisted_count,
                },
                status=status.HTTP_200_OK,
            )
            
            # For web clients, delete the cookie
            if client_type == CLIENT_TYPE_WEB:
                delete_refresh_token_cookie(response)
                logger.debug("Web client logout-all: refresh cookie deleted")
            
            return response
            
        except Exception as e:
            logger.error(f"Logout all failed for user {user.email}: {str(e)}")
            return Response(
                {"error": "Failed to logout from all devices"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

