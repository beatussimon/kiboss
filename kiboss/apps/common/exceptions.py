"""
Custom exception handler for KIBOSS API.
"""

import uuid
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status


def custom_exception_handler(exc, context):
    """
    Custom exception handler that returns consistent error format.
    """
    # Get standard error response
    response = exception_handler(exc, context)
    
    if response is not None:
        # Generate request ID
        request = context.get('request')
        request_id = getattr(request, 'request_id', str(uuid.uuid4()))
        
        # Build error response
        error_data = {
            'error': {
                'code': getattr(exc, 'default_code', 'error'),
                'message': str(exc.detail) if hasattr(exc, 'detail') else str(exc),
                'request_id': request_id,
                'timestamp': timezone.now().isoformat(),
            }
        }
        
        # Add validation errors if present
        if hasattr(exc, 'detail') and isinstance(exc.detail, dict):
            error_data['error']['details'] = exc.detail
        
        response.data = error_data
    
    return response


from django.utils import timezone
