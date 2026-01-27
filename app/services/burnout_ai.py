from app.services.openrouter_client import call_openrouter
from sqlalchemy.orm import Session
from app.models.employee import Employee
from app.models.performance_metric import PerformanceMetric
import json
import re
import logging
from datetime import datetime, timedelta, date

# Configure logger
logger = logging.getLogger(__name__)

def analyze_work_patterns(employee_id: int, db: Session) -> dict:
    """Analyze work patterns for irregularities."""
    try:
        # Fetch recent metrics
        cutoff = datetime.now() - timedelta(days=30)
        metrics = db.query(PerformanceMetric).filter(
            PerformanceMetric.employee_id == employee_id,
            PerformanceMetric.date >= cutoff
        ).all()
        
        # Simple logic for pattern detection
        overtime_days = 0
        weekend_work = 0
        
        for m in metrics:
            if m.metric_type == "work_hours" and m.value > 9:
                overtime_days += 1
            
            # Check for weekends
            # Handle both string (from some legacy DBs) and date objects
            metric_date = m.date
            if isinstance(metric_date, str):
                try:
                    metric_date = datetime.strptime(metric_date, "%Y-%m-%d").date()
                except:
                    pass
            
            if hasattr(metric_date, 'weekday') and metric_date.weekday() >= 5: # 5=Saturday, 6=Sunday
                weekend_work += 1
                
        return {
            "overtime_days": overtime_days,
            "weekend_work": weekend_work,
            "total_metrics": len(metrics)
        }
    except Exception as e:
        logger.error(f"Error in analyze_work_patterns: {str(e)}")
        return {"overtime_days": 0, "weekend_work": 0, "total_metrics": 0}

def calculate_burnout_risk(employee_id: int, db: Session) -> dict:
    """
    Calculate burnout risk using AI analysis of metrics and patterns.
    """
    try:
        # Try to get employee details, but don't block if missing
        employee = db.query(Employee).filter(Employee.id == employee_id).first()
        employee_name = employee.name if employee else f"Employee {employee_id}"
            
        patterns = analyze_work_patterns(employee_id, db)
        
        # Get recent metrics string for AI
        metrics = db.query(PerformanceMetric).filter(
            PerformanceMetric.employee_id == employee_id
        ).order_by(PerformanceMetric.date.desc()).limit(20).all()
        
        if not metrics:
            logger.info(f"No metrics found for employee {employee_id}")
            return {
                "risk_level": "unknown",
                "indicators": ["No data available"],
                "recommendations": ["Start tracking work hours to enable analysis"],
                "analysis": "Insufficient data to perform analysis."
            }
        
        metrics_str = "\n".join([f"{m.date}: {m.metric_type} = {m.value}" for m in metrics])
        
        logger.info(f"Analyzing burnout for {employee_name} ({employee_id}). Pattern: {patterns}")
        
        messages = [
            {
                "role": "system",
                "content": """You are an HR AI expert specializing in burnout detection. Analyze the employee's work data.
                Risk Levels: low, medium, high, critical.
                
                CRITICAL: You must respond in valid JSON format only. Do not wrap in markdown code blocks.
                Format: {"risk_level": "...", "indicators": ["..."], "recommendations": ["..."], "analysis": "..."}"""
            },
            {
                "role": "user",
                "content": f"""Employee: {employee_name}
                Work Patterns (Last 30 days): Overtime Days: {patterns['overtime_days']}, Weekend Work: {patterns['weekend_work']}, Total Records: {patterns['total_metrics']}
                Recent Metrics:
                {metrics_str}
                
                Analyze for burnout risk based on overtime, irregular hours, and workload consistency."""
            }
        ]
        
        response = call_openrouter(messages, temperature=0.4)
        logger.info(f"AI Response received: {response[:100]}...")
        
        try:
            # Clean response of markdown code blocks if present
            clean_response = response.strip()
            if clean_response.startswith("```json"):
                clean_response = clean_response[7:]
            if clean_response.startswith("```"):
                clean_response = clean_response[3:]
            if clean_response.endswith("```"):
                clean_response = clean_response[:-3]
            
            # Find JSON object
            json_match = re.search(r'\{.*\}', clean_response, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
                # Ensure all required keys exist
                result.setdefault("risk_level", "medium")
                result.setdefault("indicators", ["Analysis incomplete"])
                result.setdefault("recommendations", ["Review manually"])
                result.setdefault("analysis", response)
            else:
                logger.error("No JSON found in AI response")
                raise Exception("No JSON found in response")
                
        except json.JSONDecodeError as je:
            logger.error(f"JSON Parse Error: {str(je)}. Response: {response}")
            result = {
                "risk_level": "medium",
                "indicators": ["Error parsing analysis"],
                "recommendations": ["Check system logs"],
                "analysis": f"Raw AI response could not be parsed: {response}"
            }
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            result = {
                "risk_level": "medium",
                "indicators": ["Analysis Error"],
                "recommendations": ["Manual review recommended"],
                "analysis": f"Error interacting with AI: {response}"
            }
            
        return result
        
    except Exception as outer_e:
        logger.error(f"Critical error in calculate_burnout_risk: {str(outer_e)}")
        import traceback
        logger.error(traceback.format_exc())
        return {
            "risk_level": "unknown",
            "indicators": ["System Error"],
            "recommendations": ["Contact administrator"],
            "analysis": f"Internal system error: {str(outer_e)}"
        }

def generate_performance_summary(employee_id: int, db: Session) -> str:
    """Generate a summary of performance trends."""
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    employee_name = employee.name if employee else f"Employee {employee_id}"
    
    metrics = db.query(PerformanceMetric).filter(
        PerformanceMetric.employee_id == employee_id
    ).order_by(PerformanceMetric.date.desc()).limit(30).all()
    
    if not metrics:
        return "No sufficient data to generate summary."
    
    metrics_str = "\n".join([f"{m.date}: {m.metric_type} = {m.value}" for m in metrics])
    
    messages = [
        {
            "role": "system",
            "content": "Summarize the employee's performance trends based on the provided metrics. Be constructive and professional."
        },
        {
            "role": "user",
            "content": f"Employee: {employee_name}\nData:\n{metrics_str}"
        }
    ]
    
    return call_openrouter(messages)
