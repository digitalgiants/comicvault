class OllamaError(Exception):
    """Base class for all local Ollama identification errors."""


class OllamaUnreachableError(OllamaError):
    """Raised when the ollama service can't be reached at all."""


class OllamaTimeoutError(OllamaError):
    """Raised when inference doesn't complete within OLLAMA_TIMEOUT_SECONDS -
    expected occasionally on CPU-only hardware, not necessarily a bug."""


class OllamaModelNotFoundError(OllamaError):
    """Raised when the configured model hasn't been pulled yet - fix with
    `docker compose exec ollama ollama pull <model>`, see tcg-scraper/README.md."""


class OllamaResponseParseError(OllamaError):
    """Raised when the model's output isn't valid JSON despite format="json" -
    smaller vision models are less reliable at strict structured output."""
