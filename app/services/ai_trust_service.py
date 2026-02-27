from typing import Any, Dict, Optional, List
from datetime import datetime
from sqlalchemy.orm import Session
from app.schemas.trust import TrustMetadata, TrustedAIResponse, ConfidenceLevel, SourceCitation
from app.services.audit import AuditService
import json
import logging

logger = logging.getLogger(__name__)

class AITrustService:
    """
    Centralized service for wrapping AI outputs with Trust Metadata 
    and ensuring strict audit logging.
    """
    def __init__(self, db: Session, organization_id: int, user_id: int, user_role: str):
        self.db = db
        self.organization_id = organization_id
        self.user_id = user_id
        self.user_role = user_role
        self.audit_service = AuditService(db)

    def wrap_and_log(
        self,
        content: Any,
        action_type: str,
        entity_type: str,
        entity_id: Optional[int] = None,
        confidence_score: float = 0.0,
        sources: List[SourceCitation] = None,
        model_name: str = "unknown",
        reasoning: Optional[str] = None,
        is_fallback: bool = False,
        fallback_reason: Optional[str] = None,
        requires_human_confirmation: bool = False,
        details: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> TrustedAIResponse:
        """
        Wraps AI content into a TrustedAIResponse and logs the event to the AuditService.
        
        Args:
            content: The main AI output (string or dict/object).
            action_type: explicit action name for audit log (e.g., 'resume_screening', 'rag_query').
            entity_type: The type of entity involved (e.g., 'resume', 'document').
            entity_id: ID of the entity.
            confidence_score: 0.0 to 1.0.
            sources: List of citations.
            model_name: Name of the AI model used.
            reasoning: Explanation of the AI's decision.
            is_fallback: Whether this is a fallback response.
            fallback_reason: Why fallback was triggered.
            details: Additional details for the audit log.
            data: Explicit structured data to include in response (overrides content inference).
            
        Returns:
            TrustedAIResponse: standardized response object.
        """
        
        # 1. Construct Trust Metadata
        if is_fallback:
            trust_metadata = TrustMetadata.fallback(reason=fallback_reason or "Unable to process request.")
            # Ensure we preserve timestamp if not set by factory (it sets it, but good to ensure consistency)
        else:
            trust_metadata = TrustMetadata.from_score(
                score=confidence_score,
                model=model_name,
                sources=sources or [],
                reasoning=reasoning,
                requires_human_confirmation=requires_human_confirmation
            )

        # 2. Prepare Audit Details
        log_details = details or {}
        log_details.update({
            "confidence_score": confidence_score,
            "model": model_name,
            "is_fallback": is_fallback,
            "trust_metadata": trust_metadata.model_dump()
        })

        # 3. Log to AuditService
        # We catch exceptions here to ensure the user still gets the response 
        # even if logging fails (though in high-security mode we might want to fail hard)
        try:
            self.audit_service.log_action(
                action=action_type,
                entity_type=entity_type,
                entity_id=entity_id,
                user_id=self.user_id,
                user_role=self.user_role,
                details=log_details,
                ai_recommended=True,
                organization_id=self.organization_id,
                after_state={"trust_metadata": trust_metadata.model_dump()}
            )
        except Exception as e:
            logger.error(f"CRITICAL: Failed to audit AI action {action_type}: {e}", exc_info=True)
            # In a real production system, you might want to alert Sentry/Datadog here.

        # 4. Return Standardized Response
        # If content is a Pydantic model or dict, we might want to serialize it or keep it as data.
        # TrustedAIResponse expects 'content' as str (usually the main text) and 'data' for structured info.
        
        response_content = ""
        response_data = data

        if response_data is None:
            if isinstance(content, str):
                response_content = content
            elif hasattr(content, "model_dump"):
                 # It's a Pydantic model
                 response_data = content.model_dump()
                 response_content = "Structured AI Response"
            elif isinstance(content, dict):
                response_data = content
                response_content = "Structured AI Response"
            else:
                response_content = str(content)
        else:
            # Data was explicitly provided, so content must be the string message
            response_content = str(content)

        return TrustedAIResponse(
            content=response_content,
            trust=trust_metadata,
            data=response_data
        )
