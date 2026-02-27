from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from pydantic import BaseModel, ConfigDict, Field
from datetime import datetime, timezone

T = TypeVar("T")

class ErrorInfo(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None

class ApiResponse(BaseModel, Generic[T]):
    model_config = ConfigDict(json_encoders={datetime: lambda v: v.isoformat()})
    
    success: bool
    data: Optional[T] = None
    error: Optional[ErrorInfo] = None
    metadata: Dict[str, Any] = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary with JSON-serializable values."""
        return self.model_dump(mode="json")

    @classmethod
    def ok(cls, data: T, metadata: Dict[str, Any] = {}) -> "ApiResponse[T]":
        return cls(success=True, data=data, metadata=metadata)

    @classmethod
    def fail(cls, message: str, code: str = "ERROR", details: Optional[Dict[str, Any]] = None) -> "ApiResponse[T]":
        return cls(
            success=False, 
            error=ErrorInfo(code=code, message=message, details=details)
        )
