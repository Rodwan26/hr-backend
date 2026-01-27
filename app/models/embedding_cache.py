from sqlalchemy import Column, Integer, String, DateTime, PickleType
from sqlalchemy.sql import func
from app.database import Base

class EmbeddingCache(Base):
    __tablename__ = "embeddings_cache"
    
    id = Column(Integer, primary_key=True, index=True)
    text_hash = Column(String, unique=True, index=True)
    embedding_vector = Column(PickleType)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
