import logging

import requests

from app.core.config import settings

logger = logging.getLogger(__name__)

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def call_openrouter(messages: list, temperature: float = 0.7) -> str:
    """
    Call OpenRouter API with the specified messages.

    Args:
        messages: List of message dictionaries with 'role' and 'content'
        temperature: Temperature for the model (default 0.7)

    Returns:
        str: The AI response content

    Raises:
        ValueError: If API key is not configured.
        requests.HTTPError: If the API call fails.
    """
    api_key = settings.ai.openrouter_api_key
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is not configured. Set it in the environment.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": settings.ai.model_name,
        "messages": messages,
        "temperature": temperature,
    }

    response = requests.post(OPENROUTER_URL, json=payload, headers=headers, timeout=30)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
