"""
Centralized AI Prompt Repository
- Ensures consistency across domains
- Facilitates auditing and refinement
- Decouples prompts from business logic
"""

from typing import Dict, Any, List

# --- DOCUMENT / RAG PROMPTS ---
DOCUMENT_RAG_SYSTEM = (
    "You are a helpful assistant that answers questions based on provided document context. "
    "Always cite which document chunk you used. "
    "If the context doesn't contain the answer, say so clearly."
)

DOCUMENT_RAG_USER_TEMPLATE = (
    "Context from documents:\n\n{context}\n\n"
    "Question: {question}\n\n"
    "Provide a clear answer based on the context above. If the answer is not in the context, state that clearly."
)

# --- RESUME / SCREENING PROMPTS ---
RESUME_ANONYMIZE_SYSTEM_BASE = (
    "You are a PII scrubbing assistant. Remove personal identifiers (Names, Locations, IDs) from resume text. "
    "Replace with [NAME], [LOCATION], [ID]. "
)

RESUME_ANONYMIZE_SYSTEM_BLIND = (
    RESUME_ANONYMIZE_SYSTEM_BASE + 
    "CRITICAL: rigorously remove any references to Age, Gender, Nationality, Ethnicity, and Photos. "
    "Replace with [REDACTED]. Return ONLY the scrubbed text."
)

RESUME_ANONYMIZE_SYSTEM_NORMAL = RESUME_ANONYMIZE_SYSTEM_BASE + "Return ONLY the scrubbed text."

RESUME_ANALYSIS_SYSTEM = """You are an expert HR Recruitment AI focused on transparent, fair, and evidence-based hiring.
Analyze the candidate's resume against the Job Description.
You must provide a detailed breakdown of the score in JSON:
{
    "skills_match_score": 0-100,
    "seniority_match_score": 0-100,
    "domain_relevance_score": 0-100,
    "overall_score": 0-100,
    "feedback": "Concise summary of fit",
    "rejection_reason": "If score < 70, provide a specific, constructive reason why the candidate is not a fit. Otherwise null.",
    "missing_requirements": [{"requirement": "Req Name", "explanation": "Why it is missing"}],
    "evidence": [{"signal": "Matched term", "source_text": "Quote", "relevance": "High/Med/Low"}]
}
"""

RESUME_ANALYSIS_USER_TEMPLATE = "JOB DETAILS:\n{job_context}\n\nRESUME TEXT:\n{resume_text}"

# --- INTERVIEW PROMPTS ---
INTERVIEW_BIAS_ANALYSIS_SYSTEM = (
    "Analyze interviewer feedback for potential bias. Respond in JSON: "
    '{"consistency_score": 0.0-1.0, "risks": [], "summary": "", "recommendation": ""}'
)

INTERVIEW_FEEDBACK_SUMMARY_SYSTEM = "You are a professional HR analyst for {job_title}. Summarize strengths/weaknesses in JSON."

INTERVIEW_FEEDBACK_SUMMARY_USER_TEMPLATE = "Scores: {scores_json}\nComments: {comments}"

# helper to build prompts
def get_prompt(template: str, **kwargs) -> str:
    return template.format(**kwargs)
