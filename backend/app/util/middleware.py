"""
Middleware for request/response logging and context management.

Provides comprehensive request tracking with structured logging including:
- Request ID generation and propagation
- Request/response timing
- Request body logging (with sensitive data sanitization)
- Error tracking and correlation
"""

import json
import time
from typing import Any, Dict, Optional
from uuid import uuid4

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from .logging import LoggerMixin, set_request_id, clear_request_context, get_request_id


class LoggingMiddleware(BaseHTTPMiddleware, LoggerMixin):
    """
    Middleware to handle request/response logging with structured data.
    
    Features:
    - Automatic request ID generation and tracking
    - Request/response timing
    - Request body logging with sanitization
    - Error correlation
    - Performance monitoring
    """
    
    def __init__(self, app: ASGIApp, excluded_paths: Optional[list[str]] = None):
        """
        Initialize logging middleware.
        
        Args:
            app: ASGI application
            excluded_paths: List of paths to exclude from detailed logging
        """
        super().__init__(app)
        LoggerMixin.__init__(self)
        self.excluded_paths = excluded_paths or ['/health', '/docs', '/openapi.json', '/redoc']
    
    async def dispatch(self, request: Request, call_next) -> Response:
        """Process request with comprehensive logging."""
        # Skip all detailed logging for excluded paths
        if request.url.path in self.excluded_paths:
            return await call_next(request)
        
        # Generate or extract request ID
        request_id = request.headers.get('x-request-id', str(uuid4()))
        set_request_id(request_id)
        
        # Record request start time
        start_time = time.time()
        
        # Prepare request data for logging
        # **MODIFICATION**: Do not read body for streaming chat endpoint
        request_data = {}
        if request.url.path != "/chat":
            request_data = await self._prepare_request_data(request)
        
        # Log request received
        self._log_info(
            "HTTP request received",
            event_type="http_request",
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=str(request.query_params) if request.query_params else None,
            user_agent=request.headers.get('user-agent'),
            client_ip=self._get_client_ip(request),
            content_length=request.headers.get('content-length'),
            **request_data
        )
        
        response = None
        error_occurred = False
        
        try:
            # Process request
            response = await call_next(request)
            
        except Exception as e:
            error_occurred = True
            duration_ms = (time.time() - start_time) * 1000
            
            # Log error
            self._log_error(
                "HTTP request failed with exception",
                exc_info=e,
                event_type="http_request_error",
                request_id=request_id,
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error_type=type(e).__name__,
                error_message=str(e)
            )
            
            # Clean up context before re-raising
            clear_request_context()
            raise
        
        finally:
            # Calculate request duration
            duration_ms = (time.time() - start_time) * 1000
            
            if not error_occurred and response:
                # Log successful response
                self._log_info(
                    "HTTP request completed",
                    event_type="http_response",
                    request_id=request_id,
                    method=request.method,
                    path=request.url.path,
                    status_code=response.status_code,
                    duration_ms=round(duration_ms, 2),
                    response_headers=dict(response.headers) if hasattr(response, 'headers') else None
                )
            
            # Clean up request context
            clear_request_context()
        
        # Add request ID to response headers for tracing
        if response and request_id:
            response.headers['x-request-id'] = request_id
        
        return response
    
    async def _prepare_request_data(self, request: Request) -> Dict[str, Any]:
        """
        Extract and sanitize request data for logging.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Dictionary of request data safe for logging
        """
        request_data = {}
        
        # Try to read and log request body for POST/PUT/PATCH requests
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Read the body
                body = await request.body()
                
                if body:
                    # Try to parse as JSON
                    try:
                        body_data = json.loads(body.decode('utf-8'))
                        # Store sanitized version for logging
                        request_data['request_body'] = self._sanitize_request_body(body_data)
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        # If not JSON, log the content type and size
                        request_data['request_body_info'] = {
                            'content_type': request.headers.get('content-type', 'unknown'),
                            'size_bytes': len(body)
                        }
                
                # Important: Replace the request body stream so it can be read again by the endpoint
                async def receive():
                    return {"type": "http.request", "body": body}
                
                request._receive = receive
                
            except Exception as e:
                self._log_warning(
                    "Failed to read request body for logging",
                    error=str(e),
                    content_type=request.headers.get('content-type')
                )
        
        return request_data
    
    def _sanitize_request_body(self, body_data: Any) -> Any:
        """
        Sanitize request body data by removing sensitive information.
        
        Args:
            body_data: Request body data to sanitize
            
        Returns:
            Sanitized version of the data
        """
        if isinstance(body_data, dict):
            sanitized = {}
            sensitive_keys = {'password', 'token', 'secret', 'key', 'auth', 'credential', 'api_key'}
            
            for key, value in body_data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    sanitized[key] = '***REDACTED***'
                elif isinstance(value, dict):
                    sanitized[key] = self._sanitize_request_body(value)
                elif isinstance(value, list):
                    sanitized[key] = [self._sanitize_request_body(item) for item in value]
                else:
                    sanitized[key] = value
            
            return sanitized
        
        elif isinstance(body_data, list):
            return [self._sanitize_request_body(item) for item in body_data]
        
        return body_data
    
    def _get_client_ip(self, request: Request) -> str:
        """
        Extract client IP address from request.
        
        Args:
            request: FastAPI request object
            
        Returns:
            Client IP address
        """
        # Check for forwarded IP headers (common in load balancer setups)
        forwarded_ips = request.headers.get('x-forwarded-for')
        if forwarded_ips:
            # Take the first IP in the chain
            return forwarded_ips.split(',')[0].strip()
        
        real_ip = request.headers.get('x-real-ip')
        if real_ip:
            return real_ip
        
        # Fall back to client IP from connection
        if hasattr(request, 'client') and request.client:
            return request.client.host
        
        return 'unknown'