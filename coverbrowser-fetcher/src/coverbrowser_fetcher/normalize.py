import re

# Words stripped only from the *front* of a title before comparing - "The
# Amazing Spider-Man" (GCD sometimes) vs "Amazing Spider-Man" (coverbrowser's
# index, which never seems to include leading articles) need to compare equal.
_LEADING_NOISE_WORDS = {"the", "a", "an"}


def normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace, drop a leading
    article - deliberately duplicated rather than imported from comicvault's
    backend (see app/gcd_models.py's docstring for why this project keeps
    small helpers like this independent per service rather than shared)."""
    cleaned = re.sub(r"[^a-z0-9\s]", " ", title.lower())
    words = [w for w in cleaned.split() if w]
    if words and words[0] in _LEADING_NOISE_WORDS:
        words = words[1:]
    return " ".join(words)
