import requests
import os
from dotenv import load_dotenv

load_dotenv()

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "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")
OPENROUTER_MODEL = "liquid/lfm-2.5-1.2b-thinking:free"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

def call_openrouter(messages: list, temperature: float = 0.7):
    """
    Call OpenRouter API with the specified messages.
    
    Args:
        messages: List of message dictionaries with 'role' and 'content'
        temperature: Temperature for the model (default 0.7)
    
    Returns:
        str: The AI response content
    """
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
        "temperature": temperature
    }
    
    response = requests.post(OPENROUTER_URL, json=payload, headers=headers)
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"]
