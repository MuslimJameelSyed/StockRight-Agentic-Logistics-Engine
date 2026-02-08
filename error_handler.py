"""
Error handling and logging utilities for Warehouse Putaway System
Provides centralized error handling, retry logic, and audit logging
"""
import logging
import functools
import time
from typing import Callable, Any
from datetime import datetime
import json
import os

# Setup logger
logger = logging.getLogger(__name__)


class DatabaseConnectionError(Exception):
    """Raised when database connection fails"""
    pass


class QdrantConnectionError(Exception):
    """Raised when Qdrant connection fails"""
    pass


class GeminiAPIError(Exception):
    """Raised when Gemini API fails"""
    pass


class PartNotFoundError(Exception):
    """Raised when part is not found in database"""
    pass


def retry_on_failure(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Decorator to retry a function on failure with exponential backoff

    Args:
        max_retries: Maximum number of retry attempts
        delay: Initial delay between retries (seconds)
        backoff: Multiplier for delay after each retry

    Example:
        @retry_on_failure(max_retries=3, delay=1.0)
        def fetch_data():
            ...
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            current_delay = delay
            last_exception = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries - 1:
                        logger.warning(
                            f"{func.__name__} failed (attempt {attempt + 1}/{max_retries}): {str(e)}. "
                            f"Retrying in {current_delay}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"{func.__name__} failed after {max_retries} attempts: {str(e)}"
                        )

            raise last_exception

        return wrapper
    return decorator


def log_exception(func: Callable) -> Callable:
    """
    Decorator to log exceptions with full context

    Example:
        @log_exception
        def process_part(part_id):
            ...
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.exception(
                f"Exception in {func.__name__}: {str(e)}",
                extra={
                    'function': func.__name__,
                    'args': str(args)[:200],  # Limit length
                    'kwargs': str(kwargs)[:200],
                }
            )
            raise

    return wrapper


class AuditLogger:
    """
    Audit logger for tracking all recommendations and user actions
    Logs to file for compliance and analysis
    """

    def __init__(self, log_dir: str = "logs", enabled: bool = True):
        self.log_dir = log_dir
        self.enabled = enabled

        if self.enabled:
            # Create logs directory if it doesn't exist
            os.makedirs(self.log_dir, exist_ok=True)

            # Setup audit log file handler
            audit_file = os.path.join(self.log_dir, "audit.log")
            self.audit_logger = logging.getLogger('audit')
            self.audit_logger.setLevel(logging.INFO)

            # File handler for audit logs
            handler = logging.FileHandler(audit_file, encoding='utf-8')
            handler.setFormatter(logging.Formatter(
                '%(asctime)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            ))
            self.audit_logger.addHandler(handler)
            self.audit_logger.propagate = False  # Don't propagate to root logger

    def log_recommendation(
        self,
        part_id: int,
        part_code: str,
        recommended_location: str,
        status: str,
        usage_count: int,
        usage_percentage: float,
        alternatives: list = None,
        user: str = "system"
    ):
        """Log a recommendation event"""
        if not self.enabled:
            return

        event = {
            'event_type': 'recommendation',
            'timestamp': datetime.now().isoformat(),
            'user': user,
            'part_id': part_id,
            'part_code': part_code,
            'recommended_location': recommended_location,
            'status': status,
            'usage_count': usage_count,
            'usage_percentage': usage_percentage,
            'alternatives_count': len(alternatives) if alternatives else 0
        }

        self.audit_logger.info(json.dumps(event))

    def log_override(
        self,
        part_id: int,
        part_code: str,
        recommended_location: str,
        actual_location: str,
        reason: str = None,
        user: str = "operator"
    ):
        """Log when user overrides recommendation"""
        if not self.enabled:
            return

        event = {
            'event_type': 'override',
            'timestamp': datetime.now().isoformat(),
            'user': user,
            'part_id': part_id,
            'part_code': part_code,
            'recommended_location': recommended_location,
            'actual_location': actual_location,
            'reason': reason or "Not specified"
        }

        self.audit_logger.info(json.dumps(event))
        logger.warning(f"Override: Part {part_code} - Recommended {recommended_location}, User chose {actual_location}")

    def log_error(
        self,
        error_type: str,
        error_message: str,
        part_id: int = None,
        context: dict = None
    ):
        """Log error events"""
        if not self.enabled:
            return

        event = {
            'event_type': 'error',
            'timestamp': datetime.now().isoformat(),
            'error_type': error_type,
            'error_message': error_message,
            'part_id': part_id,
            'context': context or {}
        }

        self.audit_logger.error(json.dumps(event))


# Global audit logger instance
from config import config
audit_logger = AuditLogger(enabled=config.ENABLE_AUDIT_LOG)


def safe_database_call(func: Callable) -> Callable:
    """
    Decorator for safe database operations with automatic reconnection

    Example:
        @safe_database_call
        def get_part_info(cursor, part_id):
            cursor.execute("SELECT ... WHERE id = %s", (part_id,))
            return cursor.fetchone()
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            error_msg = str(e).lower()

            # Check if it's a connection error
            if any(keyword in error_msg for keyword in ['connection', 'lost', 'timeout', 'closed']):
                logger.error(f"Database connection error in {func.__name__}: {str(e)}")
                raise DatabaseConnectionError(f"Database connection failed: {str(e)}")
            else:
                logger.error(f"Database error in {func.__name__}: {str(e)}")
                raise

    return wrapper


def safe_qdrant_call(func: Callable) -> Callable:
    """
    Decorator for safe Qdrant operations

    Example:
        @safe_qdrant_call
        def get_part_from_qdrant(qdrant, part_id):
            return qdrant.retrieve(...)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Qdrant error in {func.__name__}: {str(e)}")
            raise QdrantConnectionError(f"Qdrant operation failed: {str(e)}")

    return wrapper


def safe_gemini_call(func: Callable) -> Callable:
    """
    Decorator for safe Gemini API calls with fallback

    Example:
        @safe_gemini_call
        def generate_explanation(model, prompt):
            return model.generate_content(prompt)
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.warning(f"Gemini API error in {func.__name__}: {str(e)}. Using fallback.")
            # Return None to trigger fallback logic
            return None

    return wrapper
