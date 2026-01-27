from app.services.openrouter_client import call_openrouter
import json
import re

def suggest_interview_slot(candidate_preferences: str, interviewer_availability: str) -> list[dict]:
    """
    Suggest best interview time slots based on candidate preferences and interviewer availability.
    
    Args:
        candidate_preferences: Candidate's preferred dates/times
        interviewer_availability: Interviewer's available dates/times
    
    Returns:
        list: List of 3 suggested time slots with reasoning
    """
    messages = [
        {
            "role": "system",
            "content": "You are an intelligent interview scheduling assistant. Analyze candidate preferences and interviewer availability to suggest the best 3 time slots. Always respond in JSON format: {\"suggestions\": [{\"date\": \"YYYY-MM-DD\", \"time\": \"HH:MM\", \"reasoning\": \"explanation\"}, ...]}"
        },
        {
            "role": "user",
            "content": f"Candidate Preferences:\n{candidate_preferences}\n\nInterviewer Availability:\n{interviewer_availability}\n\nSuggest the best 3 interview time slots that match both preferences. Provide date, time, and reasoning for each suggestion in JSON format."
        }
    ]
    
    response = call_openrouter(messages, temperature=0.7)
    
    # Try to extract JSON from response
    try:
        json_match = re.search(r'\{[^{}]*"suggestions"[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            suggestions = result.get("suggestions", [])
            if len(suggestions) >= 3:
                return suggestions[:3]
            elif len(suggestions) > 0:
                return suggestions
    except:
        pass
    
    # Fallback: parse text response
    suggestions = []
    lines = response.split('\n')
    current_suggestion = {}
    
    for line in lines:
        if 'date' in line.lower() or 'time' in line.lower() or 'suggestion' in line.lower():
            # Try to extract date and time
            date_match = re.search(r'(\d{4}-\d{2}-\d{2}|\d{1,2}[/-]\d{1,2}[/-]\d{2,4})', line)
            time_match = re.search(r'(\d{1,2}:\d{2})', line)
            
            if date_match or time_match:
                if current_suggestion:
                    suggestions.append(current_suggestion)
                current_suggestion = {
                    "date": date_match.group(1) if date_match else "TBD",
                    "time": time_match.group(1) if time_match else "TBD",
                    "reasoning": line.strip()
                }
            elif current_suggestion:
                current_suggestion["reasoning"] += " " + line.strip()
    
    if current_suggestion:
        suggestions.append(current_suggestion)
    
    # Ensure we have at least 3 suggestions
    while len(suggestions) < 3:
        suggestions.append({
            "date": "TBD",
            "time": "TBD",
            "reasoning": "Additional slot to be determined"
        })
    
    return suggestions[:3]

def generate_interview_questions(job_title: str, candidate_resume: str) -> list[str]:
    """
    Generate relevant interview questions based on job title and candidate resume.
    
    Args:
        job_title: The job title
        candidate_resume: The candidate's resume text
    
    Returns:
        list: List of interview questions
    """
    messages = [
        {
            "role": "system",
            "content": "You are an expert interviewer. Generate relevant interview questions based on the job title and candidate's background. Always respond in JSON format: {\"questions\": [\"question1\", \"question2\", ...]}"
        },
        {
            "role": "user",
            "content": f"Job Title: {job_title}\n\nCandidate Resume:\n{candidate_resume}\n\nGenerate 5-7 relevant interview questions for this candidate. Respond in JSON format with a 'questions' array."
        }
    ]
    
    response = call_openrouter(messages, temperature=0.7)
    
    # Try to extract JSON from response
    try:
        json_match = re.search(r'\{[^{}]*"questions"[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            questions = result.get("questions", [])
            if questions:
                return questions
    except:
        pass
    
    # Fallback: extract questions from text
    questions = []
    lines = response.split('\n')
    for line in lines:
        line = line.strip()
        # Remove numbering and bullet points
        line = re.sub(r'^\d+[\.\)]\s*', '', line)
        line = re.sub(r'^[-*]\s*', '', line)
        if line and ('?' in line or len(line) > 20):
            questions.append(line)
    
    # Ensure we have at least 5 questions
    if len(questions) < 5:
        default_questions = [
            "Tell me about yourself and your background.",
            "Why are you interested in this position?",
            "What relevant experience do you have?",
            "What are your strengths?",
            "Do you have any questions for us?"
        ]
        questions.extend(default_questions[:5-len(questions)])
    
    return questions[:7]

def analyze_interview_fit(job_requirements: str, candidate_background: str) -> tuple[float, str]:
    """
    Analyze how well a candidate fits the job requirements.
    
    Args:
        job_requirements: The job requirements
        candidate_background: The candidate's background/resume
    
    Returns:
        tuple: (fit_score: float 0-100, reasoning: str)
    """
    messages = [
        {
            "role": "system",
            "content": "You are an expert recruiter. Analyze how well a candidate fits the job requirements. Provide a fit score (0-100) and detailed reasoning. Always respond in JSON format: {\"fit_score\": <number>, \"reasoning\": \"<explanation>\"}"
        },
        {
            "role": "user",
            "content": f"Job Requirements:\n{job_requirements}\n\nCandidate Background:\n{candidate_background}\n\nAnalyze the candidate's fit for this position. Provide a score (0-100) and detailed reasoning in JSON format."
        }
    ]
    
    response = call_openrouter(messages, temperature=0.5)
    
    # Try to extract JSON from response
    try:
        json_match = re.search(r'\{[^{}]*"fit_score"[^{}]*"reasoning"[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            fit_score = float(result.get("fit_score", 50))
            reasoning = result.get("reasoning", "No reasoning provided.")
        else:
            # Fallback: try to extract score from text
            score_match = re.search(r'(?:fit|score|rating)[\s:]*(\d+(?:\.\d+)?)', response, re.IGNORECASE)
            fit_score = float(score_match.group(1)) if score_match else 50.0
            reasoning = response
    except:
        # Fallback parsing
        score_match = re.search(r'(\d+(?:\.\d+)?)', response)
        fit_score = float(score_match.group(1)) if score_match and float(score_match.group(1)) <= 100 else 50.0
        reasoning = response if response else "Analysis completed."
    
    # Ensure score is between 0 and 100
    fit_score = max(0, min(100, fit_score))
    
    return fit_score, reasoning
