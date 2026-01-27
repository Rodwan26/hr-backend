from app.services.openrouter_client import call_openrouter
from sqlalchemy.orm import Session
from app.models.activity import Activity
from app.models.employee import Employee
import json
import re

def analyze_risk(employee_id: int, db: Session) -> dict:
    """
    Analyze employee activities for potential risks.
    
    Args:
        employee_id: The employee ID to analyze
        db: Database session
    
    Returns:
        dict: Risk analysis with risk_level and details
    """
    # Get employee
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    if not employee:
        return {"risk_level": "unknown", "details": "Employee not found"}
    
    # Get all activities for this employee
    activities = db.query(Activity).filter(Activity.employee_id == employee_id).order_by(Activity.timestamp.desc()).all()
    
    if not activities:
        return {"risk_level": "low", "details": "No activities found for this employee"}
    
    # Build activity context
    activity_context = "\n\n".join([
        f"Activity {i+1}:\nType: {a.type}\nContent: {a.content}\nTimestamp: {a.timestamp}"
        for i, a in enumerate(activities[:20])  # Limit to last 20 activities
    ])
    
    messages = [
        {
            "role": "system",
            "content": "You are a risk assessment expert. Analyze employee activities for potential risks (workplace safety, policy violations, toxic behavior, etc.). Respond in JSON format: {\"risk_level\": \"low|medium|high\", \"details\": \"<explanation>\"}"
        },
        {
            "role": "user",
            "content": f"Employee: {employee.name} ({employee.email})\n\nActivities:\n{activity_context}\n\nAnalyze these activities for potential risks and provide risk level and details in JSON format."
        }
    ]
    
    response = call_openrouter(messages, temperature=0.5)
    
    # Try to extract JSON from response
    try:
        json_match = re.search(r'\{[^{}]*"risk_level"[^{}]*"details"[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            risk_level = result.get("risk_level", "low").lower()
            details = result.get("details", "No details provided.")
        else:
            # Fallback parsing
            risk_level = "medium"
            if "high" in response.lower():
                risk_level = "high"
            elif "low" in response.lower():
                risk_level = "low"
            details = response
    except:
        risk_level = "medium"
        details = response if response else "Analysis completed."
    
    # Ensure valid risk level
    if risk_level not in ["low", "medium", "high"]:
        risk_level = "medium"
    
    return {"risk_level": risk_level, "details": details}

def check_toxicity(text: str) -> dict:
    """
    Check if text contains toxic language.
    
    Args:
        text: The text to check
    
    Returns:
        dict: Toxicity check with is_toxic and explanation
    """
    messages = [
        {
            "role": "system",
            "content": "You are a content moderation expert. Check if text contains toxic, harmful, or inappropriate language. Respond in JSON format: {\"is_toxic\": true/false, \"explanation\": \"<reason>\"}"
        },
        {
            "role": "user",
            "content": f"Text to check: {text}\n\nAnalyze this text for toxicity and respond in JSON format."
        }
    ]
    
    response = call_openrouter(messages, temperature=0.3)
    
    # Try to extract JSON from response
    try:
        json_match = re.search(r'\{[^{}]*"is_toxic"[^{}]*"explanation"[^{}]*\}', response, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
            is_toxic = result.get("is_toxic", False)
            explanation = result.get("explanation", "No explanation provided.")
        else:
            # Fallback parsing
            is_toxic = "toxic" in response.lower() or "yes" in response.lower()[:50]
            explanation = response
    except:
        is_toxic = False
        explanation = response if response else "Analysis completed."
    
    return {"is_toxic": bool(is_toxic), "explanation": explanation}
