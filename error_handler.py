import logging
import traceback
from functools import wraps
from flask import jsonify, request
import sentry_sdk
from sentry_sdk.integrations.flask import FlaskIntegration
import os
from datetime import datetime

# Initialize Sentry for error monitoring
if os.environ.get('SENTRY_DSN'):
    sentry_sdk.init(
        dsn=os.environ.get('SENTRY_DSN'),
        integrations=[FlaskIntegration()],
        traces_sample_rate=1.0
    )

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - [%(filename)s:%(lineno)d] - %(request_id)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

class AppError(Exception):
    """Base application error class"""
    def __init__(self, message, status_code=500, error_code=None, details=None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details

class ValidationError(AppError):
    """Validation errors"""
    def __init__(self, message, details=None):
        super().__init__(message, 400, 'VALIDATION_ERROR', details)

class ExternalAPIError(AppError):
    """External API errors"""
    def __init__(self, message, service_name, details=None):
        super().__init__(message, 502, 'EXTERNAL_API_ERROR', details)
        self.service_name = service_name

class PaymentError(AppError):
    """Payment processing errors"""
    def __init__(self, message, details=None):
        super().__init__(message, 402, 'PAYMENT_ERROR', details)

def error_handler(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
        extra = {'request_id': request_id}
        
        try:
            return f(*args, **kwargs)
        except AppError as e:
            logger.warning(f"Application error: {e.message}", extra=extra, exc_info=True)
            return jsonify({
                'status': 'error',
                'message': e.message,
                'error_code': e.error_code,
                'details': e.details,
                'request_id': request_id
            }), e.status_code
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}", extra=extra, exc_info=True)
            sentry_sdk.capture_exception(e)
            return jsonify({
                'status': 'error',
                'message': 'Internal server error',
                'error_code': 'INTERNAL_ERROR',
                'request_id': request_id
            }), 500
    return decorated_function

def log_execution_time(operation_name):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = datetime.now()
            request_id = request.headers.get('X-Request-ID') or str(uuid.uuid4())
            extra = {'request_id': request_id, 'operation': operation_name}
            
            logger.info(f"Starting {operation_name}", extra=extra)
            
            try:
                result = f(*args, **kwargs)
                execution_time = (datetime.now() - start_time).total_seconds()
                
                logger.info(
                    f"Completed {operation_name} in {execution_time:.2f}s", 
                    extra={**extra, 'execution_time': execution_time}
                )
                
                return result
            except Exception as e:
                execution_time = (datetime.now() - start_time).total_seconds()
                logger.error(
                    f"Failed {operation_name} after {execution_time:.2f}s", 
                    extra={**extra, 'execution_time': execution_time},
                    exc_info=True
                )
                raise
        return decorated_function
    return decorator
