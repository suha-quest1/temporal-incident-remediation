import os
from groq import AsyncGroq

_client = None


def get_groq_client() -> AsyncGroq:
    """Lazy singleton — only instantiated when first needed inside an activity."""
    global _client
    if _client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY environment variable is not set")
        _client = AsyncGroq(api_key=api_key)
    return _client
