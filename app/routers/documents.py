from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel, ConfigDict
from app.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.organization import Organization
from app.services.document_ai import process_uploaded_file, query_documents, delete_document
from datetime import datetime
import os
import logging
import time

logger = logging.getLogger(__name__)

from app.routers.auth_deps import require_role, require_any_role, get_current_user, get_current_org
from app.models.user import UserRole, User
from app.services.audit import AuditService
from app.services.ai_trust_service import AITrustService
from app.schemas.trust import TrustedAIResponse, TrustMetadata

router = APIRouter(prefix="/documents", tags=["documents"])

class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    filename: str
    file_path: str
    file_type: str
    upload_date: datetime
    uploaded_by: Optional[str]
    organization_id: Optional[int]

class DocumentQueryRequest(BaseModel):
    question: str
    document_ids: Optional[List[int]] = None

class DocumentQueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    confidence: float

class ChunkResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    document_id: int
    chunk_text: str
    chunk_index: int

# Multi-tenancy is now enforced via current_user.organization_id.
# Legacy helper get_or_create_default_company removed.

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN, UserRole.HR_STAFF]))
):
    """
    Upload a company document (PDF, DOCX, TXT, CSV).
    """
    upload_start = time.time()
    logger.info("=" * 60)
    logger.info("DOCUMENT UPLOAD REQUEST RECEIVED")
    logger.info(f"Filename: {file.filename}")
    logger.info(f"Content type: {file.content_type if hasattr(file, 'content_type') else 'unknown'}")
    logger.info(f"Company ID: {current_user.organization_id}, Uploaded by: {current_user.email}")
    logger.info("=" * 60)
    
    try:
        # Process file for organization
        document = await process_uploaded_file(file, org_id, current_user.email, db)
        
        upload_time = time.time() - upload_start
        logger.info("=" * 60)
        logger.info(f"UPLOAD SUCCESSFUL - Document ID: {document.id}")
        logger.info(f"Total upload time: {upload_time:.2f}s")
        logger.info("=" * 60)
        
        # Audit logging
        AuditService.log(
            db,
            action="upload_document",
            entity_type="document",
            entity_id=document.id,
            user_id=current_user.id,
            user_role=current_user.role,
            details={"filename": file.filename, "company_id": org_id}
        )
        
        return document
        
    except ValueError as e:
        upload_time = time.time() - upload_start
        logger.error("=" * 60)
        logger.error(f"UPLOAD FAILED - Validation Error")
        logger.error(f"Error: {str(e)}")
        logger.error(f"Time before failure: {upload_time:.2f}s")
        logger.error("=" * 60)
        raise HTTPException(status_code=400, detail=str(e))
        
    except Exception as e:
        upload_time = time.time() - upload_start
        logger.error("=" * 60)
        logger.error(f"UPLOAD FAILED - Unexpected Error")
        logger.error(f"Error: {str(e)}", exc_info=True)
        logger.error(f"Time before failure: {upload_time:.2f}s")
        logger.error("=" * 60)
        raise HTTPException(status_code=500, detail=f"Error processing file: {str(e)}")

@router.post("/query", response_model=TrustedAIResponse)
def query_document(
    request: DocumentQueryRequest,
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_any_role)
):
    """
    Ask a question about company documents using RAG.
    Returns a trusted, audited AI response.
    """
    try:
        # 1. Provide Organization Context
        trust_service = AITrustService(
            db, 
            organization_id=org_id,
            user_id=current_user.id,
            user_role=current_user.role
        )

        # 2. Call AI Logic
        result = query_documents(
            request.question,
            org_id,
            db,
            top_k=5,
            document_ids=request.document_ids
        )
        
        # 3. Extract metadata from AI result
        trust_obj: TrustMetadata = result.get("trust_metadata_obj")
        if not trust_obj:
            # Should not happen given previous refactor, but safety first
            trust_obj = TrustMetadata.fallback("Internal error: AI metadata missing")
            return trust_service.wrap_and_log(
                content=result.get("answer", "Error"),
                action_type="query_document",
                entity_type="document",
                is_fallback=True,
                fallback_reason="Metadata missing"
            )

        # 4. Wrap and Log via Trust Service
        # This handles Audit Logging automatically
        return trust_service.wrap_and_log(
            content=result["answer"],
            action_type="query_document",
            entity_type="document",
            entity_id=None, # or maybe the first source doc id?
            confidence_score=trust_obj.confidence_score,
            sources=trust_obj.sources,
            model_name=trust_obj.ai_model,
            reasoning=trust_obj.reasoning,
            is_fallback=trust_obj.is_fallback,
            fallback_reason=trust_obj.fallback_reason,
            details={"question": request.question}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying documents: {str(e)}")

@router.get("", response_model=List[DocumentResponse])
def list_documents(
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_any_role)
):
    """
    List all documents for the user's organization.
    """
    documents = db.query(Document).filter(
        Document.organization_id == org_id
    ).order_by(Document.upload_date.desc()).all()
    return documents

@router.delete("/{document_id}")
def delete_document_endpoint(
    document_id: int,
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(require_role([UserRole.HR_ADMIN]))
):
    """
    Delete a document and all its chunks within organization.
    """
    success = delete_document(document_id, org_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Audit logging
    AuditService.log(
        db,
        action="delete_document",
        entity_type="document",
        entity_id=document_id,
        user_id=current_user.id,
        user_role=current_user.role,
        details={"document_id": document_id, "company_id": org_id}
    )
    
    return {"message": "Document deleted successfully"}

@router.get("/{document_id}/chunks", response_model=List[ChunkResponse])
def get_document_chunks(
    document_id: int,
    db: Session = Depends(get_db),
    org_id: int = Depends(get_current_org),
    current_user: User = Depends(get_current_user)
):
    """
    Get all chunks for a document within the user's organization.
    """
    # Verify document belongs to user's organization
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.organization_id == org_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).order_by(DocumentChunk.chunk_index).all()
    
    return chunks
