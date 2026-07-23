from app.domain.card import Card, Rank, Suit


def test_ten_card_displays_as_10_with_visible_suit():
    card = Card(suit=Suit.SPADE, rank=Rank.TEN)

    assert str(card) == "[10♠️]"


def test_heart_card_displays_as_visible_heart():
    card = Card(suit=Suit.HEART, rank=Rank.ACE)

    assert str(card) == "[A♥️]"