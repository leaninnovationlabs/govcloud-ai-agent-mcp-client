"""
Structured logging utility for the GovCloud AI Agent POC.

This module provides a comprehensive logging solution following best practices from:
- Effective Python book recommendations
- structlog documentation
- Production-ready logging patterns

Features:
- JSON structured logging for production
- Human-readable logging for development  
- Request ID tracking across operations
- Performance timing logging
- Exception handling with stack traces
- Configurable log levels per component
"""

import logging
import os
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional
from uuid import uuid4

import structlog
from structlog.typing import EventDict


class LogProcessor:
    """Custom log processors for structured logging."""
    
    _thread_local = threading.local()
    
    @staticmethod
    def add_service_info(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
        """Add service identification information to log entries."""
        event_dict.update({
            'service_name': 'govcloud-ai-agent-poc',
            'service_type': 'api',
            'service_version': '1.0.0',
            'thread_id': threading.current_thread().name,
        })
        return event_dict
    
    @staticmethod
    def add_request_id(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
        """Add request ID to log entries if available."""
        request_id = getattr(LogProcessor._thread_local, 'request_id', None)
        if request_id:
            event_dict['request_id'] = request_id
        return event_dict
    
    @staticmethod
    def add_performance_info(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
        """Add performance timing information."""
        start_time = getattr(LogProcessor._thread_local, 'operation_start_time', None)
        if start_time and 'operation_duration_ms' not in event_dict:
            duration_ms = (time.time() - start_time) * 1000
            event_dict['operation_duration_ms'] = round(duration_ms, 2)
        return event_dict
    
    @staticmethod
    def sanitize_sensitive_data(logger: Any, method_name: str, event_dict: EventDict) -> EventDict:
        """Remove or mask sensitive information from logs."""
        sensitive_keys = {'password', 'token', 'secret', 'key', 'auth', 'credential'}
        
        def _sanitize_dict(data: Dict[str, Any]) -> Dict[str, Any]:
            """Recursively sanitize dictionary values."""
            sanitized = {}
            for key, value in data.items():
                if any(sensitive in key.lower() for sensitive in sensitive_keys):
                    sanitized[key] = '***REDACTED***'
                elif isinstance(value, dict):
                    sanitized[key] = _sanitize_dict(value)
                elif isinstance(value, list):
                    sanitized[key] = [_sanitize_dict(item) if isinstance(item, dict) else item for item in value]
                else:
                    sanitized[key] = value
            return sanitized
        
        # Sanitize the event dictionary itself
        for key in list(event_dict.keys()):
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                event_dict[key] = '***REDACTED***'
            elif isinstance(event_dict[key], dict):
                event_dict[key] = _sanitize_dict(event_dict[key])
        
        return event_dict
    
    @staticmethod
    def set_request_id(request_id: str) -> None:
        """Set request ID in thread-local storage."""
        LogProcessor._thread_local.request_id = request_id
    
    @staticmethod
    def clear_request_id() -> None:
        """Clear request ID from thread-local storage."""
        if hasattr(LogProcessor._thread_local, 'request_id'):
            delattr(LogProcessor._thread_local, 'request_id')
    
    @staticmethod
    def set_operation_start_time() -> None:
        """Set operation start time for performance tracking."""
        LogProcessor._thread_local.operation_start_time = time.time()
    
    @staticmethod
    def clear_operation_start_time() -> None:
        """Clear operation start time."""
        if hasattr(LogProcessor._thread_local, 'operation_start_time'):
            delattr(LogProcessor._thread_local, 'operation_start_time')


class LoggerMixin:
    """Mixin class to provide structured logging capabilities to any class."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._logger = structlog.get_logger(self.__class__.__module__ + '.' + self.__class__.__name__)
    
    def _log_info(self, message: str, **kwargs) -> None:
        """Log an info level message with structured data."""
        self._logger.info(message, **kwargs)
    
    def _log_debug(self, message: str, **kwargs) -> None:
        """Log a debug level message with structured data."""
        self._logger.debug(message, **kwargs)
    
    def _log_warning(self, message: str, **kwargs) -> None:
        """Log a warning level message with structured data."""
        self._logger.warning(message, **kwargs)
    
    def _log_error(self, message: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """Log an error level message with optional exception info."""
        if exc_info:
            kwargs['exc_info'] = exc_info
        self._logger.error(message, **kwargs)
    
    def _log_operation_start(self, operation: str, **kwargs) -> None:
        """Log the start of an operation with timing."""
        LogProcessor.set_operation_start_time()
        self._log_info(f"Operation started: {operation}", operation=operation, **kwargs)
    
    def _log_operation_complete(self, operation: str, **kwargs) -> None:
        """Log the completion of an operation with timing."""
        self._log_info(f"Operation completed: {operation}", operation=operation, **kwargs)
        LogProcessor.clear_operation_start_time()
    
    def _log_operation_error(self, operation: str, exc_info: Optional[Exception] = None, **kwargs) -> None:
        """Log an operation error with timing and exception info."""
        self._log_error(f"Operation failed: {operation}", exc_info=exc_info, operation=operation, **kwargs)
        LogProcessor.clear_operation_start_time()
    
    @contextmanager
    def _log_operation(self, operation: str, **kwargs):
        """Context manager for logging operation start/completion with timing."""
        self._log_operation_start(operation, **kwargs)
        try:
            yield
            self._log_operation_complete(operation, **kwargs)
        except Exception as e:
            self._log_operation_error(operation, exc_info=e, **kwargs)
            raise


def configure_logging(log_level: str = "INFO", log_mode: str = "JSON") -> None:
    """
    Configure structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR)
        log_mode: Logging mode (JSON for production, LOCAL for development)
    """
    # Configure standard library logging
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        stream=sys.stdout,
        format="%(message)s"
    )
    
    # Suppress noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    
    # Configure structlog processors based on environment
    if log_mode.upper() == "LOCAL":
        # Development configuration - human readable
        processors = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="%Y-%m-%d %H:%M:%S.%f"),
            LogProcessor.add_service_info,
            LogProcessor.add_request_id,
            LogProcessor.add_performance_info,
            LogProcessor.sanitize_sensitive_data,
            structlog.processors.StackInfoRenderer(),
            # Note: format_exc_info removed for pretty exceptions in development
            structlog.dev.ConsoleRenderer(colors=True)
        ]
    else:
        # Production configuration - JSON structured
        processors = [
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            LogProcessor.add_service_info,
            LogProcessor.add_request_id,
            LogProcessor.add_performance_info,
            LogProcessor.sanitize_sensitive_data,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,  # Keep for production JSON logs
            structlog.processors.JSONRenderer()
        ]
    
    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Get a configured structured logger instance."""
    return structlog.get_logger(name)


# Convenience functions for request tracking
def set_request_id(request_id: Optional[str] = None) -> str:
    """Set or generate a request ID for the current request context."""
    if request_id is None:
        request_id = str(uuid4())
    LogProcessor.set_request_id(request_id)
    return request_id


def clear_request_context() -> None:
    """Clear all request-specific context from thread-local storage."""
    LogProcessor.clear_request_id()
    LogProcessor.clear_operation_start_time()


def get_request_id() -> Optional[str]:
    """Get the current request ID if available."""
    return getattr(LogProcessor._thread_local, 'request_id', None) 