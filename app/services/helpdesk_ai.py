from app.services.openrouter_client import call_openrouter

def answer_question(question: str, policies: list) -> str:
    """
    Answer a help desk question using policies as context.
    
    Args:
        question: The user's question
        policies: List of Policy objects with title, content, and category
    
    Returns:
        str: AI-generated answer based on policies
    """
    # Build context from policies
    policy_context = "\n\n".join([
        f"Policy: {p.title}\nCategory: {p.category}\nContent: {p.content}"
        for p in policies
    ])
    
    if not policy_context:
        policy_context = "No policies available."
    
    messages = [
        {
            "role": "system",
            "content": "You are a helpful HR help desk assistant. Answer questions based on the provided company policies. Be concise and accurate."
        },
        {
            "role": "user",
            "content": f"Company Policies:\n{policy_context}\n\nQuestion: {question}\n\nPlease provide a helpful answer based on the policies above."
        }
    ]
    
    return call_openrouter(messages, temperature=0.7)
