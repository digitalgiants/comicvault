class MetronError(Exception):
    """Base class for all Metron client errors."""


class MetronAuthError(MetronError):
    """Raised on 401 - bad or missing credentials."""


class MetronNotFoundError(MetronError):
    """Raised on 404 - no matching record."""


class MetronRateLimitError(MetronError):
    """Raised on 429 - burst (20/min) or sustained (5000/day) limit exceeded."""
