import json
import re
import requests
from typing import List, Dict, Any, Optional
from app.core.config import settings
from app.core.exceptions import AIError, AIKillSwitchError
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.core.logging import request_id_var
from app.services.audit import AuditService

logger = logging.getLogger(__name__)

class AIDomain:
    INTERVIEW = "interview"
    RESUME = "resume"
    WELLBEING = "wellbeing"
    AUDIT = "audit"
    DOCUMENTS = "documents"
    GENERAL = "general"

class AIOrchestrator:
    @staticmethod
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((requests.exceptions.RequestException, AIError)),
        reraise=True
    )
    def _do_call(
        messages: List[Dict[str, str]], 
        model_name: str,
        temperature: float = 0.7,
        json_output: bool = True
    ) -> str:
        """Internal method to perform the actual API call with retries."""
        logger.info(f"Calling AI Model: {model_name}")
        
        try:
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.ai.openrouter_api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "http://localhost:3000", # Required by OpenRouter
                },
                data=json.dumps({
                    "model": model_name,
                    "messages": messages,
                    "temperature": temperature
                }),
                timeout=30
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            
            if json_output:
                # Basic JSON extraction if model returns text around it
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json_match.group()
            
            return content

        except requests.exceptions.Timeout:
            logger.error("AI service timeout.")
            raise AIError("AI service reached timeout limit.")
        except requests.exceptions.HTTPError as e:
            logger.error(f"AI service HTTP error: {e}")
            raise AIError(f"AI service returned error: {e.response.status_code}")
        except Exception as e:
            logger.exception("Unexpected error during AI call.")
            raise AIError(f"AI service error: {str(e)}")

    @classmethod
    def call_model(
        cls,
        messages: List[Dict[str, str]], 
        temperature: float = 0.7,
        json_output: bool = True,
        domain: str = AIDomain.GENERAL,
        organization_id: Optional[int] = None,
        db_session: Any = None
    ) -> str:
        """
        Centralized AI model caller with kill-switch, retries, fallback, and domain coordination.
        """
        logger.info(f"AI Coordination Request | Domain: {domain}")
        
        if settings.ai.kill_switch:
            logger.warning("AI Kill-switch is active. Blocking request.")
            raise AIKillSwitchError()

        if not settings.ai.openrouter_api_key:
            logger.error("OpenRouter API Key missing.")
            raise AIError("AI service configuration error.")

        try:
            # Try primary model
            response = cls._do_call(messages, settings.ai.model_name, temperature, json_output)
            
            # Governance Hook: Log provenance if DB session is provided
            if db_session:
                cls._log_governance(
                    db_session, 
                    domain, 
                    messages, 
                    response, 
                    settings.ai.model_name, 
                    organization_id
                )
            
            return response
        except Exception as e:
            logger.warning(f"Primary model {settings.ai.model_name} failed: {e}. Attempting fallback.")
            try:
                # Try fallback model
                return cls._do_call(messages, settings.ai_fallback_model, temperature, json_output)
            except Exception as fe:
                logger.error(f"Fallback model {settings.ai_fallback_model} also failed: {fe}")
                raise AIError(f"AI service completely unavailable (Primary: {e}, Fallback: {fe})")

    @classmethod
    def analyze_text(
        cls, 
        system_prompt: str, 
        user_content: str, 
        temperature: float = 0.5,
        domain: str = AIDomain.GENERAL,
        organization_id: Optional[int] = None,
        db_session: Any = None
    ) -> Dict[str, Any]:
        """ Helper for common analysis tasks that expect JSON back. """
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content}
        ]
        response_text = cls.call_model(
            messages, 
            temperature=temperature, 
            json_output=True, 
            domain=domain,
            organization_id=organization_id,
            db_session=db_session
        )
        try:
            return json.loads(response_text)
        except json.JSONDecodeError:
            logger.error(f"Failed to decode AI JSON response: {response_text}")
            raise AIError("Failed to parse AI response.")

    @classmethod
    def coordinate(cls, domain: str, task: str, context: Dict[str, Any], organization_id: Optional[int] = None, db_session: Any = None) -> Any:
        """
        High-level domain-task coordination.
        In the future, this will handle complex multi-step domain workflows.
        """
        logger.info(f"Coordinating {task} in domain {domain}")
        # Current implementation just routes to analyze_text/call_model
        # But this serves as the enterprise entry point for domain logic
        if domain == AIDomain.INTERVIEW:
             # Example: Special logic for interview domain can go here
             pass
        
        return self.analyze_text(
            system_prompt=f"You are an AI coordinator for {domain}.",
            user_content=f"Task: {task}\nContext: {json.dumps(context)}",
            domain=domain,
            organization_id=organization_id,
            db_session=db_session
        )

    @classmethod
    def _log_governance(
        cls, 
        db: Any, 
        domain: str, 
        inputs: List[Dict], 
        output: str, 
        model_name: str, 
        org_id: Optional[int]
    ):
        """Internal helper to log ethical auditing data."""
        try:
            from app.models.governance import EthicalAuditLog, AIModelRegistry
            
            # Find active model version
            registry_entry = db.query(AIModelRegistry).filter(
                AIModelRegistry.domain == domain,
                AIModelRegistry.model_name == model_name,
                AIModelRegistry.is_active == True
            ).first()
            
            # Basic bias/ethical check (simulated for now)
            # In production, this would call a dedicated safety/bias model or library
            bias_score = 0.0
            if "reject" in output.lower() or "deny" in output.lower():
                bias_score = 0.2
            
            log_entry = EthicalAuditLog(
                organization_id=org_id,
                domain=domain,
                request_id=request_id_var.get(),
                model_version_id=registry_entry.id if registry_entry else None,
                input_data_summary={"messages": inputs},
                output_data={"text": output},
                confidence_score=0.9, # Simulated
                bias_score=bias_score,
                flagged_for_review=bias_score > 0.5,
                ethical_checks={"automated_bias_check": True}
            )
            db.add(log_entry)
            try:
                db.commit()
            except Exception:
                db.rollback()
                raise
            
            if bias_score > 0.5:
                AuditService.log(
                    db,
                    action="high_bias_detected",
                    entity_type="ai_governance",
                    entity_id=log_entry.id,
                    user_id=None,
                    user_role="ai_system",
                    details={"score": bias_score, "request_id": log_entry.request_id},
                    organization_id=org_id
                )
        except Exception as e:
            logger.error(f"Failed to log AI governance data: {e}")
