"""
Standardized Trust Metadata for AI Outputs.
All AI services should include this metadata in their responses
to ensure enterprise-grade explainability and auditability.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime, timezone
from enum import Enum

class ConfidenceLevel(str, Enum):
    HIGH = "high"       # >= 0.8
    MEDIUM = "medium"   # 0.5 - 0.8
    LOW = "low"         # < 0.5

class SourceCitation(BaseModel):
    """A reference to a source document used in generating the response."""
    document_id: int
    filename: str
    chunk_index: int
    snippet: Optional[str] = None
    similarity_score: float = Field(default=0.0, ge=0.0, le=1.0)
    version: Optional[str] = None  # Document version
    source_date: Optional[str] = None # Document upload/creation date

class TrustMetadata(BaseModel):
    """
    Standardized trust metadata attached to all AI-generated outputs.
    Ensures explainability, traceability, and compliance.
    """
    # Confidence
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_level: ConfidenceLevel = ConfidenceLevel.LOW
    
    # Sources/Citations
    sources: List[SourceCitation] = Field(default_factory=list)
    
    # Model Information
    ai_model: str = "unknown"
    model_version: Optional[str] = None
    
    # Provenance
    reasoning: Optional[str] = None
    timestamp: Optional[str] = None
    request_id: Optional[str] = None
    
    # Human-in-the-loop
    requires_human_confirmation: bool = False
    
    # Fallback indicator
    is_fallback: bool = False
    fallback_reason: Optional[str] = None
    
    @classmethod
    def from_score(cls, score: float, model: str = "unknown", sources: List[SourceCitation] = None, **kwargs) -> "TrustMetadata":
        """Factory method to create TrustMetadata from a confidence score."""
        if score >= 0.8:
            level = ConfidenceLevel.HIGH
        elif score >= 0.5:
            level = ConfidenceLevel.MEDIUM
        else:
            level = ConfidenceLevel.LOW
        
        return cls(
            confidence_score=score,
            confidence_level=level,
            ai_model=model,
            sources=sources or [],
            timestamp=datetime.now(timezone.utc).isoformat(),
            **kwargs
        )
    
    @classmethod
    def fallback(cls, reason: str = "I couldn't find this information in the available documents.") -> "TrustMetadata":
        """Factory method for fallback responses when AI can't answer."""
        return cls(
            confidence_score=0.0,
            confidence_level=ConfidenceLevel.LOW,
            is_fallback=True,
            fallback_reason=reason,
            timestamp=datetime.now(timezone.utc).isoformat()
        )

class TrustedAIResponse(BaseModel):
    """
    Wrapper for any AI-generated response that includes trust metadata.
    Use this as the standard response format for AI endpoints.
    """
    content: str  # The actual AI-generated content
    trust: TrustMetadata
    
    # Optional structured data (for JSON responses)
    data: Optional[dict] = None

# Resolve forward references for Pydantic V2
TrustMetadata.model_rebuild()
TrustedAIResponse.model_rebuild()
SourceCitation.model_rebuild()

