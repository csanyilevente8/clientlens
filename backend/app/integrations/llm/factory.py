"""Provider selection by configuration (SPEC §46).

The rest of the app calls get_llm_provider() and does not care which implementation it is.
Adding OpenAI/Anthropic later = a new module + a branch here, no business-logic changes.
"""

from functools import lru_cache

from app.core.config import get_settings
from app.integrations.llm.base import LLMProvider
from app.integrations.llm.mock import MockLLMProvider


@lru_cache
def get_llm_provider() -> LLMProvider:
    provider = get_settings().llm_provider.lower()
    if provider == "mock":
        return MockLLMProvider()
    # Future: "anthropic" -> AnthropicProvider(), "openai" -> OpenAIProvider()
    raise ValueError(f"Unsupported LLM_PROVIDER: {provider!r}")
