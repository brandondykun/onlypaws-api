"""
HTTP Request Logging Middleware

Logs all HTTP requests with method, path, status code, and response time.
"""

import logging
import time

logger = logging.getLogger('django.request')


class RequestLoggingMiddleware:
    """
    Middleware to log HTTP requests and responses.
    
    Logs:
    - HTTP method (GET, POST, etc.)
    - Request path
    - Response status code
    - Response time in seconds
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Record start time
        start_time = time.time()
        
        # Process the request
        response = self.get_response(request)
        
        # Calculate response time
        duration = time.time() - start_time
        
        # Log the request
        logger.info(
            f"{request.method} {request.path} {response.status_code} [{duration:.3f}s]"
        )
        
        return response

