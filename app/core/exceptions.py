from typing import Any, Dict, Optional

class AppException(Exception):
    def __init__(
        self, 
        message: str, 
        status_code: int = 400, 
        error_code: str = "BUSINESS_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.status_code = status_code
        self.error_code = error_code
        self.details = details
        super().__init__(self.message)

class AIError(AppException):
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            message=message, 
            status_code=503, 
            error_code="AI_SERVICE_UNAVAILABLE",
            details=details
        )

class AIKillSwitchError(AppException):
    def __init__(self):
        super().__init__(
            message="AI services are currently offline for maintenance.",
            status_code=503,
            error_code="AI_KILL_SWITCH_ACTIVE"
        )

class AuthenticationError(AppException):
    def __init__(self, message: str = "Could not validate credentials"):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AUTH_FAILED"
        )

class AccessDeniedError(AppException):
    """Custom permission error. Named AccessDeniedError to avoid shadowing Python's built-in PermissionError."""
    def __init__(self, message: str = "Insufficient permissions"):
        super().__init__(
            message=message,
            status_code=403,
            error_code="PERMISSION_DENIED"
        )
