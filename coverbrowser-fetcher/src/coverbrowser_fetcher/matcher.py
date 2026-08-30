"""Matches a GCD series against coverbrowser's crawled series index.

Scoped to series with `year_began` before a cutoff (2011 by default - see
cli.py) because coverbrowser's own coverage appears to stop around the
2011-era relaunch wave for most flagship titles: a real check during design
found coverbrowser's "batman" slug caps out at its classic Volume 1 run
(#1-713, ending 2011) with no New 52 or Rebirth content at all, and no
separate slug for those later volumes exists in its index either. Modern
series aren't worth spending request budget checking.

coverbrowser exposes no publisher and no per-issue cover date anywhere (a
real per-cover sample was checked - just an issue number and an image path).
That rules out the date/publisher cross-checks this design originally
assumed would be available, so acceptance leans on: (1) an exact,
unambiguous title match, (2) a plausible cover-count, and (3) a live
verification fetch (crawler.verify_first_issue_present) confirming the
candidate's page 1 actually contains the series' first issue number - see
cli.py's `match` command, which runs that check before persisting an "auto"
result. Anything short of all three goes to manual review rather than being
guessed.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from coverbrowser_fetcher.crawler import IndexEntry
from coverbrowser_fetcher.gcd_read import GcdSeriesSummary
from coverbrowser_fetcher.normalize import normalize_title

# A coverbrowser cover count includes variants/reprints, so it's expected to
# run somewhat higher than GCD's issue_count - only flag it when the ratio is
# implausible in either direction.
_MIN_PLAUSIBLE_RATIO = 0.5
_MAX_PLAUSIBLE_RATIO = 3.0


@dataclass
class MatchCandidate:
    slug: str
    title_raw: str
    cover_count_hint: int | None
    score: float
    reasons: list[str] = field(default_factory=list)


@dataclass
class MatchResult:
    gcd_series_id: int
    gcd_series_name: str
    status: str  # "auto" | "review" | "no_match"
    accepted: MatchCandidate | None
    candidates: list[MatchCandidate]
    reason: str  # "unique_match" | "no_match" | "ambiguous" | "count_implausible"


def build_index_by_title(entries: list[IndexEntry]) -> dict[str, list[IndexEntry]]:
    index: dict[str, list[IndexEntry]] = {}
    for entry in entries:
        index.setdefault(normalize_title(entry.title_raw), []).append(entry)
    return index


def find_candidates(series: GcdSeriesSummary, index_by_title: dict[str, list[IndexEntry]]) -> list[MatchCandidate]:
    entries = index_by_title.get(normalize_title(series.name), [])
    candidates = [_score(series, entry) for entry in entries]
    candidates.sort(key=lambda c: -c.score)
    return candidates


def _score(series: GcdSeriesSummary, entry: IndexEntry) -> MatchCandidate:
    reasons = ["exact_title_match"]
    score = 1.0
    if entry.cover_count_hint is not None and series.issue_count:
        ratio = entry.cover_count_hint / series.issue_count
        if ratio < _MIN_PLAUSIBLE_RATIO or ratio > _MAX_PLAUSIBLE_RATIO:
            score -= 1.0
            reasons.append(f"cover_count_implausible(cb={entry.cover_count_hint},gcd={series.issue_count})")
        else:
            reasons.append("plausible_cover_count")
    return MatchCandidate(
        slug=entry.slug, title_raw=entry.title_raw, cover_count_hint=entry.cover_count_hint,
        score=score, reasons=reasons,
    )


def decide(series: GcdSeriesSummary, candidates: list[MatchCandidate]) -> MatchResult:
    """Structural decision only - does not fetch anything. cli.py's `match`
    command still runs a live verification fetch on an "auto" result before
    persisting it (see module docstring); that can downgrade this decision
    to "review" but never upgrade a "review" to "auto"."""
    if not candidates:
        return MatchResult(series.id, series.name, "no_match", None, [], "no_match")
    if len(candidates) > 1:
        return MatchResult(series.id, series.name, "review", None, candidates, "ambiguous")
    only = candidates[0]
    if only.score < 1.0:
        return MatchResult(series.id, series.name, "review", None, candidates, "count_implausible")
    return MatchResult(series.id, series.name, "auto", only, candidates, "unique_match")
