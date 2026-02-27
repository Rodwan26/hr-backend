from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel, ConfigDict
from app.database import get_db
from app.models.policy import Policy
from app.models.ticket import Ticket
from app.services.helpdesk_ai import answer_question
from datetime import datetime

from app.routers.auth_deps import require_role, require_any_role, get_current_org
from app.models.user import UserRole, User
from app.services.ai_trust_service import AITrustService
from app.schemas.trust import TrustedAIResponse

router = APIRouter(prefix="/helpdesk", tags=["helpdesk"])

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    ticket_id: int

class TicketResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    question: str
    ai_response: str
    created_at: datetime

class PolicyCreate(BaseModel):
    title: str
    content: str
    category: str

class PolicyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    title: str
    content: str
    category: str

@router.post("/ask", response_model=TrustedAIResponse)
def ask_question(
    request: AskRequest, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_any_role)
):
    """
    Ask a help desk question and get AI response based on organization-specific policies.
    """
    # Get all policies for the current organization
    policies = db.query(Policy).filter(Policy.organization_id == org_id).all()
    
    # Get AI answer
    try:
        ai_response = answer_question(request.question, policies)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")
    
    # Save ticket
    ticket = Ticket(
        question=request.question,
        ai_response=ai_response,
        organization_id=org_id
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    # Standardize on AITrustService for consistency
    trust_service = AITrustService(
        db,
        organization_id=org_id,
        user_id=current_user.id,
        user_role=current_user.role
    )

    return trust_service.wrap_and_log(
        content=ai_response,
        action_type="helpdesk_query",
        entity_type="ticket",
        entity_id=ticket.id,
        confidence_score=0.9, # Placeholder for helpdesk
        model_name="HR-Policy-v1",
        details={"question": request.question}
    )

@router.get("/tickets", response_model=List[TicketResponse])
def get_tickets(
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_STAFF]))
):
    """
    Get all help desk tickets for the current organization.
    """
    tickets = db.query(Ticket).filter(
        Ticket.organization_id == org_id
    ).order_by(Ticket.created_at.desc()).all()
    return tickets

@router.post("/policies", response_model=PolicyResponse)
def create_policy(
    policy: PolicyCreate, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_STAFF]))
):
    """
    Create a new policy.
    """
    db_policy = Policy(
        title=policy.title,
        content=policy.content,
        category=policy.category,
        organization_id=org_id
    )
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy

@router.get("/policies", response_model=List[PolicyResponse])
def get_policies(
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_any_role)
):
    """
    Get all policies for the current organization.
    """
    policies = db.query(Policy).filter(Policy.organization_id == org_id).all()
    return policies

@router.delete("/policies/{policy_id}")
def delete_policy(
    policy_id: int, 
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN]))
):
    """
    Delete a policy by ID within organization scope.
    """
    policy = db.query(Policy).filter(
        Policy.id == policy_id,
        Policy.organization_id == org_id
    ).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    db.delete(policy)
    db.commit()
    return {"message": "Policy deleted successfully"}
