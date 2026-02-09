"""
Custom middleware for KIBOSS.
"""

import uuid
from django.utils.deprecation import MiddlewareMixin


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware for audit logging.
    Adds request_id and traces for correlation.
    """
    
    def process_request(self, request):
        """Add request ID and user info to request."""
        # Generate or get request ID
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        request.META['REQUEST_ID'] = request_id
        request.request_id = request_id
        
        # Get user if authenticated
        if hasattr(request, 'user') and request.user.is_authenticated:
            request.user_id = request.user.id
        else:
            request.user_id = None
    
    def process_response(self, request, response):
        """Add request ID to response header."""
        if hasattr(request, 'request_id'):
            response['X-Request-ID'] = request.request_id
        return response
