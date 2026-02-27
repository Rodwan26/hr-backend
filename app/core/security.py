import re
import html
import logging
from typing import Any, Dict, Optional
from cryptography.fernet import Fernet
from app.core.config import settings

logger = logging.getLogger(__name__)

# Encryption cipher initialized with SECRET_KEY
# Note: For production, use a dedicated ENCRYPTION_KEY separate from the JWT secret
_cipher = Fernet(settings.encryption_key if hasattr(settings, 'encryption_key') else Fernet.generate_key())

def encrypt_data(data: str) -> str:
    """Encrypt sensitive string data."""
    if not data:
        return data
    try:
        return _cipher.encrypt(data.encode()).decode()
    except Exception as e:
        logger.error(f"Encryption failed: {e}")
        raise ValueError(f"Encryption failed — refusing to store plaintext: {e}") from e

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive string data."""
    if not encrypted_data:
        return encrypted_data
    try:
        return _cipher.decrypt(encrypted_data.encode()).decode()
    except Exception as e:
        logger.warning(f"Decryption failed (possibly not encrypted): {e}")
        return encrypted_data

def sanitize_input(text: str) -> str:
    """Basic input sanitization to prevent XSS."""
    if not isinstance(text, str):
        return text
    # Escape HTML characters
    sanitized = html.escape(text)
    # Remove potentially dangerous script tags or attributes (basic)
    sanitized = re.sub(r'<script.*?>.*?</script>', '', sanitized, flags=re.DOTALL | re.IGNORECASE)
    return sanitized

def sanitize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Recursively sanitize a dictionary payload."""
    sanitized = {}
    for key, value in payload.items():
        if isinstance(value, str):
            sanitized[key] = sanitize_input(value)
        elif isinstance(value, dict):
            sanitized[key] = sanitize_payload(value)
        elif isinstance(value, list):
            sanitized[key] = [sanitize_payload(v) if isinstance(v, dict) else sanitize_input(v) if isinstance(v, str) else v for v in value]
        else:
            sanitized[key] = value
    return sanitized
