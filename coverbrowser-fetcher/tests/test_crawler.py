from pathlib import Path

from coverbrowser_fetcher.crawler import parse_az_index_page, parse_series_page, verify_first_issue_present

FIXTURES = Path(__file__).parent / "fixtures"


class _FakeClient:
    def __init__(self, html: str):
        self._html = html
        self.requested_paths: list[str] = []

    def get(self, path: str) -> str:
        self.requested_paths.append(path)
        return self._html


def test_parse_az_index_page_reads_slug_title_and_count():
    html = (FIXTURES / "az_index_b_excerpt.html").read_text()
    entries = parse_az_index_page(html)

    by_slug = {e.slug: e for e in entries}
    assert set(by_slug) == {
        "b1n4ry", "babe", "baby-huey-and-papa", "backlash", "badaxe", "badger",
        "batman", "batman-robin-adventures",
    }
    assert by_slug["badger"].title_raw == "Badger"
    assert by_slug["badger"].cover_count_hint == 70


def test_parse_az_index_page_unescapes_html_entities_in_title():
    html = (FIXTURES / "az_index_b_excerpt.html").read_text()
    entries = {e.slug: e for e in parse_az_index_page(html)}
    assert entries["batman-robin-adventures"].title_raw == "Batman & Robin Adventures"


def test_parse_az_index_page_strips_publisher_icon_from_title():
    html = (FIXTURES / "az_index_b_excerpt.html").read_text()
    entries = {e.slug: e for e in parse_az_index_page(html)}
    # "Babe" has a <img .../> icon before the title text in the real markup -
    # it must not leak into title_raw.
    assert entries["babe"].title_raw == "Babe"


def test_parse_series_page_reads_title_and_issue_numbers():
    html = (FIXTURES / "series_badaxe.html").read_text()
    page = parse_series_page(html)

    assert page.title_raw == "Badaxe"
    assert [i.number for i in page.issues] == ["1", "2", "3"]
    assert [i.image_path for i in page.issues] == [
        "/image/badaxe/1-1.jpg", "/image/badaxe/2-1.jpg", "/image/badaxe/3-1.jpg",
    ]


def test_verify_first_issue_present_true_when_issue_one_is_on_the_page():
    client = _FakeClient((FIXTURES / "series_badaxe.html").read_text())
    assert verify_first_issue_present(client, "badaxe") is True
    assert client.requested_paths == ["/covers/badaxe"]


def test_verify_first_issue_present_false_when_expected_issue_is_absent():
    client = _FakeClient((FIXTURES / "series_badaxe.html").read_text())
    # Series page starts at #1 in this fixture - a GCD series claiming to
    # start at #100 would be a red flag, not this same slug.
    assert verify_first_issue_present(client, "badaxe", expected_number="100") is False
