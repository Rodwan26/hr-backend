from sqlalchemy.orm import Session
from app.models.payroll import Payroll, PayrollStatus
from app.models.salary_component import SalaryComponent, ComponentType
from app.models.payroll_policy import PayrollPolicy, CalculationType
from typing import Dict, Any, List, Optional
from app.services.openrouter_client import call_openrouter
import json

class PayrollAIService:
    def calculate_payroll(self, db: Session, employee_id: str, month: int, year: int, base_salary: float) -> Payroll:
        """
        Calculate payroll for an employee for a specific month.
        """
        # Check if payroll already exists
        existing_payroll = db.query(Payroll).filter(
            Payroll.employee_id == employee_id,
            Payroll.month == month,
            Payroll.year == year
        ).first()

        if existing_payroll:
            return existing_payroll

        # Get policies
        policies = db.query(PayrollPolicy).all()

        components: List[SalaryComponent] = []
        
        # Base Salary Component
        components.append(SalaryComponent(
            component_type=ComponentType.BASE,
            name="Base Salary",
            amount=base_salary,
            description="Monthly Base Salary"
        ))

        total_bonus = 0.0
        total_deduction = 0.0

        # Apply policies (Mock logic for applying policies)
        for policy in policies:
            amount = 0.0
            if policy.calculation_type == CalculationType.FIXED:
                amount = policy.default_value
            elif policy.calculation_type == CalculationType.PERCENTAGE:
                amount = base_salary * (policy.default_value / 100)
            
            # Identify if it's a bonus or deduction based on name/convention or add type to policy in future
            # For now, let's assume "Tax" and "Insurance" are deductions, others are allowances (bonuses)
            if "tax" in policy.component_name.lower() or "insurance" in policy.component_name.lower():
                c_type = ComponentType.DEDUCTION
                total_deduction += amount
            else:
                 c_type = ComponentType.ALLOWANCE # Treated as bonus for net calculation
                 total_bonus += amount

            components.append(SalaryComponent(
                component_type=c_type,
                name=policy.component_name,
                amount=amount,
                description=f"Automated calculation based on {policy.calculation_type}"
            ))

        net_salary = base_salary + total_bonus - total_deduction

        payroll = Payroll(
            employee_id=employee_id,
            month=month,
            year=year,
            base_salary=base_salary,
            bonuses=total_bonus,
            deductions=total_deduction,
            net_salary=net_salary,
            status=PayrollStatus.DRAFT
        )
        
        db.add(payroll)
        db.flush() # flush to get ID

        for comp in components:
            comp.payroll_id = payroll.id
            db.add(comp)
        
        db.commit()
        db.refresh(payroll)
        return payroll

    def explain_payslip(self, payroll: Payroll) -> Dict[str, Any]:
        """
        AI explains the payslip details.
        """
        components_str = "\n".join([f"{c.name}: {c.amount} ({c.component_type})" for c in payroll.components])
        
        messages = [
            {
                "role": "system",
                "content": "You are a helpful Payroll Assistant. Explain the payslip to the employee in a clear, friendly manner."
            },
            {
                "role": "user",
                "content": f"""
                Explain this payslip for {payroll.month}/{payroll.year}:
                Base Salary: {payroll.base_salary}
                Net Salary: {payroll.net_salary}
                
                Components:
                {components_str}
                
                Provide a summary and explain any significant deductions or bonuses.
                """
            }
        ]
        
        explanation = call_openrouter(messages)
        return {"explanation": explanation}

    def answer_payroll_question(self, question: str, context: Optional[str] = None) -> str:
        """
        Answer general or specific payroll questions.
        """
        messages = [
            {
                "role": "system",
                "content": "You are an expert HR Payroll Assistant. Answer questions accurately and concisely."
            },
            {
                "role": "user",
                "content": f"Question: {question}\nContext (if any): {context}"
            }
        ]
        return call_openrouter(messages)

    def suggest_tax_optimization(self, payroll: Payroll) -> str:
        """
        Suggest tax saving tips based on payslip.
        """
        messages = [
            {
                "role": "system",
                "content": "You are a Financial Advisor for employees. Suggest legal tax optimization strategies."
            },
            {
                "role": "user",
                "content": f"""
                Review this payroll data and suggest tax saving tips (e.g. 401k, HSA, etc).
                Base: {payroll.base_salary}
                Net: {payroll.net_salary}
                Deductions: {payroll.deductions}
                """
            }
        ]
        return call_openrouter(messages)
