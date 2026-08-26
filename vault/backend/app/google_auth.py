"""Verifies Google Identity Services ID tokens (the "credential" the
frontend's Sign in with Google button hands back) - see routes/users.py's
/auth/google-login. This is a public-key signature check against Google's
own JWKS (handled by the google-auth library, including key rotation/
caching), not the server-side authorization-code exchange flow, so no
client secret is needed - only the client ID, to confirm the token was
actually issued for this app and not some other Google-integrated site.
"""

from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from app.config import settings

_google_request = google_requests.Request()


class GoogleAuthNotConfigured(Exception):
    pass


class GoogleTokenInvalid(Exception):
    pass


def verify_google_id_token(credential: str) -> dict:
    if not settings.google_client_id:
        raise GoogleAuthNotConfigured("Google sign-in is not configured")
    try:
        return id_token.verify_oauth2_token(credential, _google_request, settings.google_client_id)
    except ValueError as exc:
        raise GoogleTokenInvalid(str(exc)) from exc
