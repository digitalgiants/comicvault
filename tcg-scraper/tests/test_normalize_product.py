"""Regression tests against the exact real apitcg.com response captured in
feature-requests/apitcg-calls - not a guessed shape, an actual API call."""
from tcg_scraper.api import _normalize_product

REAL_PRODUCT = {
    "_id": 59052, "type": "card", "name": "AZ",
    "tcg": {
        "_id": "pokemon", "name": "Pokémon",
        "description": "Pokémon TCG",
        "markets": {"tcgplayer": {"id": "3"}, "tcgmatch": {"id": "pokemon"}},
        "createdAt": "2026-03-25T21:08:50.481Z", "updatedAt": "2026-03-25T23:46:16.415Z", "__v": 0,
    },
    "set": {
        "_id": "pokemon-xy-phantom-forces", "name": "XY - Phantom Forces", "tcg": "pokemon",
        "code": "PHF",
        "markets": {"tcgplayer": {"id": "1494"}, "tcgmatch": {"id": "pokemon-xy-phantom-forces"}},
        "createdAt": "2026-03-25T21:09:02.280Z", "updatedAt": "2026-08-08T00:00:06.578Z",
        "slug": "xy-phantom-forces", "__v": 0, "serie": None,
        "release_date": "2014-11-05T00:00:00.000Z",
    },
    "images": [{
        "small": "https://tcgplayer-cdn.tcgplayer.com/product/94659_200w.jpg",
        "medium": "https://tcgplayer-cdn.tcgplayer.com/product/94659_400w.jpg",
        "large": "https://tcgplayer-cdn.tcgplayer.com/product/94659_in_1000x1000.jpg",
        "_id": "6a7675db7a4d8170546fe2bf",
    }],
    "markets": {
        "tcgplayer": {
            "id": "94659",
            "url": "https://www.tcgplayer.com/product/94659/pokemon-xy-phantom-forces-az",
            "prices": {"low": 0.35, "mid": 0.65, "high": 2.99, "market": 0.73},
        },
    },
    "code": "91/119",
    "attributes": {
        "Number": "91/119", "Rarity": "Uncommon", "Card Type": "Supporter",
        "CardText": "Put 1 Pokémon into your hand. (Discard all cards attached to that Pokémon.)",
    },
    "__v": 0, "createdAt": "2026-03-25T22:39:21.188Z", "updatedAt": "2026-08-08T01:20:46.575Z",
}


def test_normalize_real_product_response():
    card = _normalize_product(REAL_PRODUCT)

    assert card.external_id == "59052"
    assert card.name == "AZ"
    # No "cardNumber" field exists on the wire - must come from "code".
    assert card.card_number == "91/119"
    assert card.code == "91/119"
    assert card.rarity == "Uncommon"
    # images is a LIST on the wire - must unwrap the first element.
    assert card.images.small == "https://tcgplayer-cdn.tcgplayer.com/product/94659_200w.jpg"
    assert card.images.large == "https://tcgplayer-cdn.tcgplayer.com/product/94659_in_1000x1000.jpg"
    # release_date lives on the embedded set, not the card itself.
    assert card.release_date == "2014-11-05T00:00:00.000Z"
    # price is nested three levels deep: markets.tcgplayer.prices.market
    assert card.average_price == 0.73
    # embedded set info, for on-the-fly set resolution during a whole-catalog sync
    assert card.set_external_id == "pokemon-xy-phantom-forces"
    assert card.set_name == "XY - Phantom Forces"
    assert card.set_code == "PHF"
    assert card.attributes["Card Type"] == "Supporter"


def test_normalize_product_missing_optional_fields_does_not_crash():
    minimal = {"_id": 1, "name": "Bare Card"}
    card = _normalize_product(minimal)
    assert card.external_id == "1"
    assert card.card_number is None
    assert card.images.small is None
    assert card.average_price is None
    assert card.set_external_id is None
