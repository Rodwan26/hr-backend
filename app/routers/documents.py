from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List, Optional
from pydantic import BaseModel
from app.database import get_db
from app.models.document import Document
from app.models.document_chunk import DocumentChunk
from app.models.company import Company
from app.services.document_ai import process_uploaded_file, query_documents, delete_document
from datetime import datetime
import os
import logging
import time

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])

class DocumentResponse(BaseModel):
    id: int
    filename: str
    file_path: str
    file_type: str
    upload_date: datetime
    uploaded_by: Optional[str]
    company_id: int
    
    class Config:
        from_attributes = True

class DocumentQueryRequest(BaseModel):
    question: str
    company_id: int
    document_ids: Optional[List[int]] = None

class DocumentQueryResponse(BaseModel):
    answer: str
    sources: List[dict]
    confidence: float

class ChunkResponse(BaseModel):
    id: int
    document_id: int
    chunk_text: str
    chunk_index: int
    
    class Config:
        from_attributes = True

# Default company ID (for single-tenant setup)
DEFAULT_COMPANY_ID = 1

def get_or_create_default_company(db: Session) -> Company:
    """Get or create default company."""
    company = db.query(Company).filter(Company.id == DEFAULT_COMPANY_ID).first()
    if not company:
        company = Company(id=DEFAULT_COMPANY_ID, name="Default Company")
        db.add(company)
        db.commit()
        db.refresh(company)
    return company

@router.post("/upload", response_model=DocumentResponse)
async def upload_document(
    file: UploadFile = File(...),
    company_id: int = Form(DEFAULT_COMPANY_ID),
    uploaded_by: str = Form("system"),
    db: Session = Depends(get_db)
):
    """
    Upload a company document (PDF, DOCX, TXT, CSV).
    """
    upload_start = time.time()
    logger.info("=" * 60)
    logger.info("DOCUMENT UPLOAD REQUEST RECEIVED")
    logger.info(f"Filename: {file.filename}")
    logger.info(f"Content type: {file.content_type if hasattr(file, 'content_type') else 'unknown'}")
    logger.info(f"Company ID: {company_id}, Uploaded by: {uploaded_by}")
    logger.info("=" * 60)
    
    try:
        # Ensure company exists
        logger.info("Ensuring company exists...")
        get_or_create_default_company(db)
        logger.info("Company verified/created")
        
        # Process file
        document = await process_uploaded_file(file, company_id, uploaded_by, db)
        
        upload_time = time.time() - upload_start
        logger.info("=" * 60)
        logger.info(f"UPLOAD SUCCESSFUL - Document ID: {document.id}")
        logger.info(f"Total upload time: {upload_time:.2f}s")
        logger.info("=" * 60)
        
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

@router.post("/query", response_model=DocumentQueryResponse)
def query_document(
    request: DocumentQueryRequest,
    db: Session = Depends(get_db)
):
    """
    Ask a question about company documents using RAG.
    """
    try:
        result = query_documents(
            request.question,
            request.company_id,
            db,
            top_k=5,
            document_ids=request.document_ids
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error querying documents: {str(e)}")

@router.get("", response_model=List[DocumentResponse])
def list_documents(
    company_id: int = DEFAULT_COMPANY_ID,
    db: Session = Depends(get_db)
):
    """
    List all documents for a company.
    """
    documents = db.query(Document).filter(
        Document.company_id == company_id
    ).order_by(Document.upload_date.desc()).all()
    return documents

@router.delete("/{document_id}")
def delete_document_endpoint(
    document_id: int,
    company_id: int = DEFAULT_COMPANY_ID,
    db: Session = Depends(get_db)
):
    """
    Delete a document and all its chunks.
    """
    success = delete_document(document_id, company_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully"}

@router.get("/{document_id}/chunks", response_model=List[ChunkResponse])
def get_document_chunks(
    document_id: int,
    company_id: int = DEFAULT_COMPANY_ID,
    db: Session = Depends(get_db)
):
    """
    Get all chunks for a document.
    """
    # Verify document belongs to company
    document = db.query(Document).filter(
        Document.id == document_id,
        Document.company_id == company_id
    ).first()
    
    if not document:
        raise HTTPException(status_code=404, detail="Document not found")
    
    chunks = db.query(DocumentChunk).filter(
        DocumentChunk.document_id == document_id
    ).order_by(DocumentChunk.chunk_index).all()
    
    return chunks
