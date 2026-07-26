from datetime import date
from unittest.mock import MagicMock, call

from comic_scraper.lookup import UpcLookupService
from comic_scraper.metron.models import Credit, Issue, PublisherRef, SeriesRef, Variant


def make_issue() -> Issue:
    return Issue(
        id=1,
        series=SeriesRef(id=1, name="Amazing Spider-Man", volume=1, year_began=1963),
        publisher=PublisherRef(id=1, name="Marvel"),
        number="1",
        cover_date=date(1963, 3, 1),
        store_date=date(1963, 1, 10),
        upc="759606086121",
        image="https://static.metron.cloud/base-cover.jpg",
        cover_hash="abc123",
        cv_id=100,
        gcd_id=200,
        variants=[
            Variant(
                name="Cover B",
                upc="75960608612100121",
                image="https://static.metron.cloud/variant-cover.jpg",
            )
        ],
        credits=[
            Credit(id=1, creator="Steve Ditko", role=[{"id": 1, "name": "Cover"}]),
            Credit(id=2, creator="Stan Lee", role=[{"id": 2, "name": "Writer"}]),
            Credit(
                id=3,
                creator="Jack Kirby",
                role=[{"id": 3, "name": "Penciller"}, {"id": 4, "name": "Inker"}],
            ),
        ],
    )


def test_lookup_cache_hit_skips_client() -> None:
    cache = MagicMock()
    cache.get.return_value = {
        "series_name": "Amazing Spider-Man",
        "issue_number": "1",
        "cover_date": "1963-03-01",
        "variant_name": None,
        "cover_artists": ["Steve Ditko"],
        "matched_on": "base_upc",
    }
    client = MagicMock()

    result = UpcLookupService(client, cache).lookup("759606086121")

    assert result is not None
    assert result.source == "cache"
    client.get_issue_by_upc.assert_not_called()


def test_lookup_queries_concatenated_upc_plus_ean5_first() -> None:
    issue = make_issue()
    cache = MagicMock()
    cache.get.return_value = None
    client = MagicMock()
    client.get_issue_by_upc.return_value = issue

    result = UpcLookupService(client, cache).lookup("759606086121", "00121")

    client.get_issue_by_upc.assert_called_once_with("75960608612100121")
    assert result is not None
    assert result.matched_on == "variant_upc"
    assert result.variant_name == "Cover B"
    assert result.cover_artists == ["Steve Ditko"]
    assert result.series_volume == 1
    assert result.publisher_name == "Marvel"
    assert result.store_date == "1963-01-10"
    assert result.writers == ["Stan Lee"]
    assert result.pencillers == ["Jack Kirby"]
    assert result.inkers == ["Jack Kirby"]
    assert {c.creator for c in result.credits} == {"Steve Ditko", "Stan Lee", "Jack Kirby"}
    assert result.metron_id == 1
    assert result.cv_id == 100
    assert result.gcd_id == 200
    assert result.image == "https://static.metron.cloud/variant-cover.jpg"
    assert result.cover_hash == "abc123"
    cache.set.assert_called_once()


def test_lookup_falls_back_to_bare_upc12_when_concatenated_code_misses() -> None:
    issue = make_issue()
    cache = MagicMock()
    cache.get.return_value = None
    client = MagicMock()
    client.get_issue_by_upc.side_effect = [None, issue]

    result = UpcLookupService(client, cache).lookup("759606086121", "00121")

    assert client.get_issue_by_upc.call_args_list == [
        call("75960608612100121"),
        call("759606086121"),
    ]
    assert result is not None


def test_lookup_without_ean5_queries_bare_upc12_only() -> None:
    issue = make_issue()
    cache = MagicMock()
    cache.get.return_value = None
    client = MagicMock()
    client.get_issue_by_upc.return_value = issue

    result = UpcLookupService(client, cache).lookup("759606086121")

    client.get_issue_by_upc.assert_called_once_with("759606086121")
    assert result is not None
    assert result.matched_on == "base_upc"
    assert result.variant_name is None
    assert result.image == "https://static.metron.cloud/base-cover.jpg"


def test_lookup_handles_missing_publisher_and_store_date() -> None:
    issue = make_issue()
    issue.publisher = None
    issue.store_date = None
    cache = MagicMock()
    cache.get.return_value = None
    client = MagicMock()
    client.get_issue_by_upc.return_value = issue

    result = UpcLookupService(client, cache).lookup("759606086121")

    assert result is not None
    assert result.publisher_name is None
    assert result.store_date is None
