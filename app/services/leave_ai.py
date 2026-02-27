from sqlalchemy.orm import Session
from app.models.leave_request import LeaveRequest, LeaveStatus
from app.models.leave_balance import LeaveBalance
from app.models.leave_policy import LeavePolicy
from typing import Dict, Any, List
from datetime import datetime
from app.services.openrouter_client import call_openrouter
import json
import logging

logger = logging.getLogger(__name__)

def check_leave_eligibility(db: Session, employee_id: str, leave_type: str, days_requested: float) -> Dict[str, Any]:
    """
    Check if employee has enough balance and meets policy requirements.
    """
    # 1. Check Balance
    balance = db.query(LeaveBalance).filter(
        LeaveBalance.employee_id == employee_id,
        LeaveBalance.leave_type == leave_type
    ).first()

    if not balance:
        return {"eligible": False, "reason": f"No leave balance record found for {leave_type}"}

    if balance.remaining_days < days_requested:
        return {
            "eligible": False, 
            "reason": f"Insufficient balance. Requested: {days_requested}, Remaining: {balance.remaining_days}"
        }

    # 2. Check Policy (basic check)
    policy = db.query(LeavePolicy).filter(LeavePolicy.leave_type == leave_type).first()
    if policy and policy.max_days_per_year and days_requested > policy.max_days_per_year:
         return {
            "eligible": False,
            "reason": f"Request exceeds policy limit of {policy.max_days_per_year} days per year."
        }
    
    return {"eligible": True, "reason": "Balance and policy checks passed.", "balance": balance, "policy": policy}

def auto_approve_decision(leave_request: LeaveRequest, balance: LeaveBalance, policy: LeavePolicy) -> Dict[str, Any]:
    """
    Use AI to decide if leave should be auto-approved using specific signals.
    """
    if not policy:
        # Default fallback if no policy
        if leave_request.days_count <= 2:
             return {"decision": "auto_approved", "reasoning": "Short duration (< 2 days) and no specific policy restrictions."}
        else:
             return {"decision": "pending_approval", "reasoning": "Duration > 2 days requires manual review."}

    # If policy allows auto-approve and request is within threshold
    if policy.auto_approve_threshold_days and leave_request.days_count <= policy.auto_approve_threshold_days:
        return {"decision": "auto_approved", "reasoning": "Within auto-approval threshold defined by policy."}
    
    # Use AI for more complex decision (e.g. "sick" leave with high frequency, or specific reasons)
    # Construct prompt
    messages = [
        {
            "role": "system",
            "content": "You are an HR Leave Administrator AI. Analyze the leave request and recommend a decision (Auto-Approve or Manual Review). Output JSON only."
        },
        {
            "role": "user",
            "content": f"""
            Analyze this leave request:
            Type: {leave_request.leave_type}
            Duration: {leave_request.days_count} days
            Reason: {leave_request.reason}
            Employee Previous Leaves (Used): {balance.used_days} days
            Policy Max Days: {policy.max_days_per_year}
            
            Key:
            - Auto-Approve if standard, reasonable, and low risk.
            - Manual Review if high duration, unusual reason, or close to limits.

            Return JSON: {{ "decision": "auto_approved" | "pending_approval", "reasoning": "string" }}
            """
        }
    ]

    try:
        response_text = call_openrouter(messages, temperature=0.2)
        # Attempt to parse specific JSON block if model is chatty
        if "```json" in response_text:
            json_str = response_text.split("```json")[1].split("```")[0].strip()
        elif "```" in response_text:
             json_str = response_text.split("```")[1].split("```")[0].strip()
        else:
            json_str = response_text.strip()
            
        ai_result = json.loads(json_str)
        return ai_result
    except Exception as e:
        logger.error(f"AI Decision Error: {e}", exc_info=True)
        # Fallback to manual review on error
        return {"decision": "pending_approval", "reasoning": "AI analysis failed, defaulted to manual review."}

def suggest_alternative_dates(start_date: str, end_date: str, reason: str) -> str:
    """
    If dates conflict (mock scenario), suggest alternatives.
    """
    messages = [
         {
            "role": "system",
            "content": "You are a helpful HR Assistant. Suggest alternative leave dates."
        },
        {
            "role": "user",
            "content": f"User requested leave from {start_date} to {end_date} for reason: '{reason}'. Assuming these dates are busy (e.g. project deadline), suggest two alternative date ranges nearby."
        }
    ]
    return call_openrouter(messages)

def calculate_leave_impact(days_count: float, leave_type: str) -> str:
    """
    Analyze impact on team.
    """
    messages = [
         {
            "role": "system",
            "content": "You are a Team Management AI. Assess the impact of an employee's absence."
        },
        {
            "role": "user",
            "content": f"Employee is taking {days_count} days of {leave_type} leave. Describe potential impacts on team workflow and 1-2 mitigation strategies."
        }
    ]
    return call_openrouter(messages)
