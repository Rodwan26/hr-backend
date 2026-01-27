from app.services.openrouter_client import call_openrouter
import json
import re

def analyze_resume(resume_text: str, job_requirements: str) -> tuple[float, str]:
    """
    Analyze a resume against job requirements and provide score and feedback.
    
    Args:
        resume_text: The resume content
        job_requirements: The job requirements
    
    Returns:
        tuple: (score: float 0-100, feedback: str)
    """
    messages = [
        {
            "role": "system",
            "content": "You are an expert resume reviewer. Analyze resumes against job requirements and provide a score (0-100) and detailed feedback. Always respond in JSON format: {\"score\": <number>, \"feedback\": \"<text>\"}"
        },
        {
            "role": "user",
            "content": f"Job Requirements:\n{job_requirements}\n\nResume:\n{resume_text}\n\nAnalyze this resume and provide a score (0-100) and detailed feedback in JSON format."
        }
    ]
    
    response = call_openrouter(messages, temperature=0.5)
    
    # Try to extract JSON from response
    try:
        # Look for JSON in the response
        json_match = re.search(r'\{[^{}]*"score"[^{}]*"feedback"[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            score = float(result.get("score", 50))
            feedback = result.get("feedback", "No feedback provided.")
        else:
            # Fallback: try to extract score from text
            score_match = re.search(r'score["\s:]*(\d+(?:\.\d+)?)', response, re.IGNORECASE)
            score = float(score_match.group(1)) if score_match else 50.0
            feedback = response
    except:
        # Fallback parsing
        score_match = re.search(r'(\d+(?:\.\d+)?)', response)
        score = float(score_match.group(1)) if score_match and float(score_match.group(1)) <= 100 else 50.0
        feedback = response if response else "Analysis completed."
    
    # Ensure score is between 0 and 100
    score = max(0, min(100, score))
    
    return score, feedback
