from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel
from app.database import get_db
from app.models.policy import Policy
from app.models.ticket import Ticket
from app.services.helpdesk_ai import answer_question
from datetime import datetime

router = APIRouter(prefix="/api/helpdesk", tags=["helpdesk"])

class AskRequest(BaseModel):
    question: str

class AskResponse(BaseModel):
    answer: str
    ticket_id: int

class TicketResponse(BaseModel):
    id: int
    question: str
    ai_response: str
    created_at: datetime
    
    class Config:
        from_attributes = True

class PolicyCreate(BaseModel):
    title: str
    content: str
    category: str

class PolicyResponse(BaseModel):
    id: int
    title: str
    content: str
    category: str
    
    class Config:
        from_attributes = True

@router.post("/ask", response_model=AskResponse)
def ask_question(request: AskRequest, db: Session = Depends(get_db)):
    """
    Ask a help desk question and get AI response based on policies.
    """
    # Get all policies for context
    policies = db.query(Policy).all()
    
    # Get AI answer
    try:
        ai_response = answer_question(request.question, policies)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"AI service error: {str(e)}")
    
    # Save ticket
    ticket = Ticket(
        question=request.question,
        ai_response=ai_response
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    
    return AskResponse(answer=ai_response, ticket_id=ticket.id)

@router.get("/tickets", response_model=List[TicketResponse])
def get_tickets(db: Session = Depends(get_db)):
    """
    Get all help desk tickets.
    """
    tickets = db.query(Ticket).order_by(Ticket.created_at.desc()).all()
    return tickets

@router.post("/policies", response_model=PolicyResponse)
def create_policy(policy: PolicyCreate, db: Session = Depends(get_db)):
    """
    Create a new policy.
    """
    db_policy = Policy(
        title=policy.title,
        content=policy.content,
        category=policy.category
    )
    db.add(db_policy)
    db.commit()
    db.refresh(db_policy)
    return db_policy

@router.get("/policies", response_model=List[PolicyResponse])
def get_policies(db: Session = Depends(get_db)):
    """
    Get all policies.
    """
    policies = db.query(Policy).all()
    return policies

@router.delete("/policies/{policy_id}")
def delete_policy(policy_id: int, db: Session = Depends(get_db)):
    """
    Delete a policy by ID.
    """
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    
    db.delete(policy)
    db.commit()
    return {"message": "Policy deleted successfully"}
