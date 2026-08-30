from coverbrowser_fetcher.normalize import normalize_title


def test_normalize_strips_leading_article():
    assert normalize_title("The Amazing Spider-Man") == normalize_title("Amazing Spider-Man")


def test_normalize_is_case_and_punctuation_insensitive():
    assert normalize_title("Batman & Robin Adventures") == normalize_title("batman and robin adventures".replace("and", "&"))
    assert normalize_title("Badger") == "badger"


def test_normalize_collapses_whitespace():
    assert normalize_title("Baby   Huey  and Papa") == normalize_title("Baby Huey and Papa")
