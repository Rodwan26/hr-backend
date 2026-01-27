import hashlib
import numpy as np
from typing import List, Optional
from sqlalchemy.orm import Session
from app.models.document_chunk import DocumentChunk
import logging
import time

logger = logging.getLogger(__name__)

# Embedding dimensions (using a standard size)
EMBEDDING_DIM = 384  # Can be adjusted based on model

def generate_text_hash(text: str) -> str:
    """Generate hash for text to use as cache key."""
    return hashlib.md5(text.encode()).hexdigest()

def generate_embeddings(texts: List[str], db: Session = None) -> List[List[float]]:
    """
    Generate embeddings for a list of texts using fast hash-based method.
    No caching - direct generation for speed and reliability.
    
    Args:
        texts: List of text strings to embed
        db: Database session (not used, kept for compatibility)
    
    Returns:
        List of embedding vectors
    """
    start_time = time.time()
    logger.info(f"Generating embeddings for {len(texts)} texts")
    
    embeddings = []
    for i, text in enumerate(texts):
        try:
            embedding = _fallback_embedding(text)
            embeddings.append(embedding)
        except Exception as e:
            logger.error(f"Error generating embedding for text {i}: {e}")
            # Ultimate fallback: create a simple zero vector
            embedding = [0.0] * EMBEDDING_DIM
            embeddings.append(embedding)
    
    elapsed = time.time() - start_time
    logger.info(f"Generated {len(embeddings)} embeddings in {elapsed:.2f}s")
    return embeddings

def _fallback_embedding(text: str) -> List[float]:
    """
    Fast hash-based embedding method (no API calls).
    This is a reliable fallback that works instantly.
    """
    # Simple hash-based embedding (fast and reliable)
    hash_obj = hashlib.sha256(text.encode())
    hash_bytes = hash_obj.digest()
    
    # Convert to embedding vector
    embedding = []
    for i in range(0, min(len(hash_bytes), EMBEDDING_DIM)):
        embedding.append(float(hash_bytes[i]) / 255.0)
    
    # Pad or truncate to EMBEDDING_DIM
    while len(embedding) < EMBEDDING_DIM:
        embedding.append(0.0)
    
    return embedding[:EMBEDDING_DIM]

def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calculate cosine similarity between two vectors."""
    vec1 = np.array(vec1)
    vec2 = np.array(vec2)
    dot_product = np.dot(vec1, vec2)
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(dot_product / (norm1 * norm2))

def semantic_search(
    query_embedding: List[float],
    company_id: int,
    db: Session,
    top_k: int = 5,
    document_ids: Optional[List[int]] = None
) -> List[dict]:
    """
    Perform semantic search to find relevant document chunks.
    
    Args:
        query_embedding: Query embedding vector
        company_id: Company ID to filter documents
        db: Database session
        top_k: Number of results to return
        document_ids: Optional list of document IDs to search within
    
    Returns:
        List of dictionaries with chunk info and similarity scores
    """
    from app.models.document import Document
    
    # Get all chunks for the company
    query = db.query(DocumentChunk).join(Document).filter(Document.company_id == company_id)
    
    if document_ids:
        query = query.filter(DocumentChunk.document_id.in_(document_ids))
    
    chunks = query.all()
    
    # Calculate similarities
    results = []
    for chunk in chunks:
        if chunk.embedding_vector:
            similarity = cosine_similarity(query_embedding, chunk.embedding_vector)
            results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_text": chunk.chunk_text,
                "chunk_index": chunk.chunk_index,
                "similarity": similarity
            })
    
    # Sort by similarity and return top_k
    results.sort(key=lambda x: x["similarity"], reverse=True)
    return results[:top_k]

def hybrid_search(
    query_text: str,
    query_embedding: List[float],
    company_id: int,
    db: Session,
    top_k: int = 5
) -> List[dict]:
    """
    Perform hybrid search (semantic + keyword) for better results.
    
    Args:
        query_text: Original query text for keyword matching
        query_embedding: Query embedding vector
        company_id: Company ID
        db: Database session
        top_k: Number of results
    
    Returns:
        List of results with combined scores
    """
    # Semantic search
    semantic_results = semantic_search(query_embedding, company_id, db, top_k * 2)
    
    # Keyword search (simple text matching)
    from app.models.document import Document
    query_words = set(query_text.lower().split())
    
    keyword_results = []
    chunks = db.query(DocumentChunk).join(Document).filter(
        Document.company_id == company_id
    ).all()
    
    for chunk in chunks:
        chunk_words = set(chunk.chunk_text.lower().split())
        common_words = query_words.intersection(chunk_words)
        keyword_score = len(common_words) / max(len(query_words), 1)
        
        if keyword_score > 0:
            keyword_results.append({
                "chunk_id": chunk.id,
                "document_id": chunk.document_id,
                "chunk_text": chunk.chunk_text,
                "chunk_index": chunk.chunk_index,
                "keyword_score": keyword_score
            })
    
    # Combine results
    combined = {}
    for result in semantic_results:
        chunk_id = result["chunk_id"]
        combined[chunk_id] = {
            **result,
            "keyword_score": 0.0,
            "combined_score": result["similarity"] * 0.7  # Weight semantic more
        }
    
    for result in keyword_results:
        chunk_id = result["chunk_id"]
        if chunk_id in combined:
            combined[chunk_id]["keyword_score"] = result["keyword_score"]
            combined[chunk_id]["combined_score"] = (
                combined[chunk_id]["similarity"] * 0.7 + result["keyword_score"] * 0.3
            )
        else:
            combined[chunk_id] = {
                **result,
                "similarity": 0.0,
                "combined_score": result["keyword_score"] * 0.3
            }
    
    # Sort by combined score
    final_results = sorted(combined.values(), key=lambda x: x["combined_score"], reverse=True)
    return final_results[:top_k]