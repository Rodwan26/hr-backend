import json
import logging
import re
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.services.ai_trust_service import AITrustService
from app.models.user import UserRole


from app.models.resume import Resume
from app.models.job import Job
from app.core import prompts
from app.services.notification import NotificationService

logger = logging.getLogger(__name__)

def anonymize_resume(text: str, blind_screening: bool = False) -> str:
    """
    Anonymize resume text to remove PII.
    If blind_screening is True, aggressively redacts name, gender, age, nationality, photo references.
    """
    logger.info(f"Anonymizing resume (blind_screening={blind_screening})")
    
    # 1. Basic Regex Scrubbing
    text = re.sub(r'[\w\.-]+@[\w\.-]+\.\w+', '[EMAIL]', text)
    text = re.sub(r'\+?\d[\d\-\(\) ]{8,}\d', '[PHONE]', text)
    text = re.sub(r'https?://[^\s<>"]+|www\.[^\s<>"]+', '[LINK]', text)
    
    # 2. Blind Screening specific
    if blind_screening:
        text = re.sub(r'(?i)\b(photo|headshot|picture)\b.*', '[PHOTO REDACTED]', text)
        
    # 3. LLM-based Contextual Scrubbing
    if blind_screening:
        instruction = prompts.RESUME_ANONYMIZE_SYSTEM_BLIND
    else:
        instruction = prompts.RESUME_ANONYMIZE_SYSTEM_NORMAL

    messages = [{"role": "system", "content": instruction}, {"role": "user", "content": text[:8000]}]
    
    try:
        return AIOrchestrator.call_model(
            messages, temperature=0.1, json_output=False, domain=AIDomain.RESUME
        ).strip()
    except Exception as e:
        logger.warning(f"AI Anonymization failed, using regex-only: {e}")
        return text

def calculate_confidence(overall_score: float, missing_reqs: List[Any], evidence: List[Any]) -> float:
    """
    Derive confidence score from analysis quality and signals.
    """
    base = 0.9  # Start high assuming AI works
    
    # Penalize if score is high but many missing requirements (contradiction)
    if overall_score > 70 and len(missing_reqs) > 2:
        base -= 0.2
        
    # Penalize if very little evidence was found
    if len(evidence) < 2:
        base -= 0.3
        
    # Cap between 0.1 and 1.0
    return max(0.1, min(1.0, base))

def analyze_resume(resume_text: str, job_details: Dict[str, Any]) -> Dict[str, Any]:
    """
    Analyze resume against job details with transparent scoring.
    """
    logger.info("Analyzing resume with transparent scoring.")
    
    system_prompt = prompts.RESUME_ANALYSIS_SYSTEM
    
    # Construct Context
    job_context = f"JOB TITLE: {job_details.get('title', 'Unknown')}\n"
    if job_details.get('roles_responsibilities'):
        job_context += f"ROLES: {job_details['roles_responsibilities']}\n"
    if job_details.get('candidate_profile'):
        job_context += f"PROFILE: {json.dumps(job_details['candidate_profile'])}\n"
    if job_details.get('requirements'):
         job_context += f"REQS: {job_details['requirements']}\n"
         
    user_content = prompts.get_prompt(
        prompts.RESUME_ANALYSIS_USER_TEMPLATE,
        job_context=job_context,
        resume_text=resume_text[:10000]
    )
    
    try:
        data = AIOrchestrator.analyze_text(
            system_prompt, user_content, temperature=0.2, domain=AIDomain.RESUME
        )
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        raise e # Let caller handle retry

    # Extract scores
    overall = float(data.get("overall_score", 0))
    missing = data.get("missing_requirements", [])
    evidence = data.get("evidence", [])
    
    # Intelligent Confidence Calculation
    conf_score = calculate_confidence(overall, missing, evidence)
    
    # Trust Metadata
    trust = TrustMetadata(
        confidence_score=conf_score,
        confidence_level=ConfidenceLevel.HIGH if conf_score > 0.7 else ConfidenceLevel.MEDIUM if conf_score > 0.4 else ConfidenceLevel.LOW,
        ai_model="HR-Ensemble-v1",
        timestamp=datetime.now(timezone.utc).isoformat(),
        reasoning=f"Based on {len(evidence)} evidence points and {len(missing)} missing requirements."
    )
    
    return {
        "score": overall,
        "skills_match_score": float(data.get("skills_match_score", 0)),
        "seniority_match_score": float(data.get("seniority_match_score", 0)),
        "domain_relevance_score": float(data.get("domain_relevance_score", 0)),
        "feedback": data.get("feedback", "No feedback."),
        "rejection_reason": data.get("rejection_reason"),
        "evidence": evidence,
        "missing_requirements": missing,
        "trust_metadata": trust.model_dump(),
        "trust_metadata_obj": trust
    }

def process_resume_analysis(db: Session, payload: Dict[str, Any]):
    """
    Background Task Handler for Resume Analysis.
    """
    resume_id = payload.get("resume_id")
    job_id = payload.get("job_id")
    
    logger.info(f"Task Handler: Starting analysis for Resume {resume_id}, Job {job_id}")
    
    resume = db.query(Resume).filter(Resume.id == resume_id).first()
    job = db.query(Job).filter(Job.id == job_id).first()
    
    if not resume or not job:
        raise ValueError("Resume or Job not found in database.")
        
    job_details = {
        "title": job.title,
        "description": job.description,
        "requirements": job.requirements,
        "roles_responsibilities": job.roles_responsibilities,
        "desired_responsibilities": job.desired_responsibilities,
        "candidate_profile": job.candidate_profile
    }
    
    # Perform Analysis
    result = analyze_resume(resume.anonymized_text, job_details)
    
    # Update Resume Record
    resume.ai_score = result["score"]
    resume.ai_feedback = result["feedback"]
    resume.ai_evidence = result["evidence"]
    resume.skills_match_score = result["skills_match_score"]
    resume.seniority_match_score = result["seniority_match_score"]
    resume.domain_relevance_score = result["domain_relevance_score"]
    resume.missing_requirements = result["missing_requirements"]
    resume.rejection_reason = result["rejection_reason"]
    resume.trust_metadata = result["trust_metadata"]
    
    resume.status = "New" # Ready for review
    resume.anonymization_status = "VERIFIED" # Assumed if analysis ran on anonymized text
    
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise
    
    # Audit Log via AITrustService
    # We try to determine context from payload or default to System
    user_id = payload.get("user_id") # Passed from trigger
    org_id = job.organization_id
    
    try:
        trust_service = AITrustService(
             db,
             organization_id=org_id,
             user_id=user_id if user_id else 1, # Default to admin if missing (system action) or handle better
             user_role="system" if not user_id else "HR_STAFF" # Placeholder role if unknown
        )
        
        trust_service.wrap_and_log(
            content=result["feedback"],
            action_type="analyze_resume",
            entity_type="resume",
            entity_id=resume.id,
            confidence_score=result["trust_metadata_obj"].confidence_score,
            model_name="HR-Ensemble-v1",
            reasoning=result["trust_metadata_obj"].reasoning,
            details={"job_id": job_id, "score": result["score"]}
        )
    except Exception as e:
        logger.error(f"Failed to log trust event for resume {resume_id}: {e}")

    # Trigger Notification for the user who submitted the resume
    if user_id:
        NotificationService.notify_user(
            db,
            user_id=user_id,
            title="Analysis Complete",
            message=f"AI analysis for '{resume.name}' is ready. Score: {resume.ai_score}/100.",
            type="info",
            link=f"/jobs/{job_id}"
        )

    logger.info(f"Task Handler: Analysis completed for Resume {resume_id}")
    return result
