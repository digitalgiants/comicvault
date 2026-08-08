class ApiTcgError(Exception):
    """Base class for all apitcg.com client errors."""


class ApiTcgAuthError(ApiTcgError):
    """Raised on 401/403 - bad or missing API key. If this fires immediately,
    check APITCG_AUTH_HEADER against apitcg.com's real Authentication docs -
    the default here (x-api-key) is unverified."""


class ApiTcgNotFoundError(ApiTcgError):
    """Raised on 404 - no matching record."""


class ApiTcgRateLimitError(ApiTcgError):
    """Raised on 429 - apitcg.com's actual rate limit is undocumented in
    what we could find; APITCG_MAX_CALLS_PER_MINUTE is a conservative guess."""


class ApiTcgQuotaExceededError(ApiTcgError):
    """Raised locally (never from apitcg.com itself) when the in-process
    monthly call counter crosses APITCG_MONTHLY_CALL_LIMIT - a soft guard
    against burning the real monthly quota (1,000 calls/month on the free
    tier) via a runaway loop or repeated sync, not a hard apitcg.com error."""
