from coverbrowser_fetcher.crawler import IndexEntry
from coverbrowser_fetcher.gcd_read import GcdSeriesSummary
from coverbrowser_fetcher.matcher import build_index_by_title, decide, find_candidates


def make_series(**overrides) -> GcdSeriesSummary:
    defaults = dict(id=1, name="Badger", publisher_name="First Comics", year_began=1985, year_ended=1991, issue_count=70)
    defaults.update(overrides)
    return GcdSeriesSummary(**defaults)


def test_unique_exact_title_match_with_plausible_count_is_auto_accepted():
    index = build_index_by_title([IndexEntry(slug="badger", title_raw="Badger", cover_count_hint=70)])
    series = make_series()

    candidates = find_candidates(series, index)
    result = decide(series, candidates)

    assert result.status == "auto"
    assert result.accepted.slug == "badger"
    assert result.reason == "unique_match"


def test_no_candidates_is_no_match():
    index = build_index_by_title([IndexEntry(slug="something-else", title_raw="Something Else", cover_count_hint=10)])
    series = make_series()

    result = decide(series, find_candidates(series, index))

    assert result.status == "no_match"
    assert result.accepted is None


def test_multiple_candidates_for_the_same_title_are_never_guessed():
    # Two unrelated real-world comics can share a normalized title - e.g. two
    # different eras/publishers both just called "Nova". Never auto-pick one.
    index = build_index_by_title([
        IndexEntry(slug="badger", title_raw="Badger", cover_count_hint=70),
        IndexEntry(slug="badger-reprint", title_raw="Badger", cover_count_hint=12),
    ])
    series = make_series()

    result = decide(series, find_candidates(series, index))

    assert result.status == "review"
    assert result.reason == "ambiguous"
    assert result.accepted is None
    assert len(result.candidates) == 2


def test_wildly_mismatched_cover_count_is_queued_not_auto_accepted():
    # GCD says 12 issues but the slug has 700+ covers - almost certainly the
    # wrong thing (a compilation/misc category, not this series).
    index = build_index_by_title([IndexEntry(slug="badger", title_raw="Badger", cover_count_hint=700)])
    series = make_series(issue_count=12)

    result = decide(series, find_candidates(series, index))

    assert result.status == "review"
    assert result.reason == "count_implausible"


def test_missing_cover_count_hint_does_not_block_a_match():
    index = build_index_by_title([IndexEntry(slug="badger", title_raw="Badger", cover_count_hint=None)])
    series = make_series()

    result = decide(series, find_candidates(series, index))

    assert result.status == "auto"


def test_title_matching_is_case_and_article_insensitive():
    index = build_index_by_title([IndexEntry(slug="amazing-spider-man", title_raw="Amazing Spider-Man", cover_count_hint=500)])
    series = make_series(name="The Amazing Spider-Man", issue_count=441)

    result = decide(series, find_candidates(series, index))

    assert result.status == "auto"
    assert result.accepted.slug == "amazing-spider-man"
