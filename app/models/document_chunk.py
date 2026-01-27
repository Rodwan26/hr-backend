from sqlalchemy import Column, Integer, String, Text, ForeignKey, PickleType
from app.database import Base

class DocumentChunk(Base):
    __tablename__ = "document_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("documents.id"), index=True)
    chunk_text = Column(Text)
    chunk_index = Column(Integer)
    embedding_vector = Column(PickleType, nullable=True)  # Store as pickle for SQLite, or use pgvector for PostgreSQL
