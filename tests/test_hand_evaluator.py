from app.domain.card import Card, Rank, Suit
from app.domain.hand_evaluator import HandEvaluator, HandRank


evaluator = HandEvaluator()


def c(rank: Rank, suit: Suit) -> Card:
    return Card(suit=suit, rank=rank)


def test_royal_flush():
    cards = [
        c(Rank.ACE, Suit.SPADE),
        c(Rank.KING, Suit.SPADE),
        c(Rank.QUEEN, Suit.SPADE),
        c(Rank.JACK, Suit.SPADE),
        c(Rank.TEN, Suit.SPADE),
        c(Rank.TWO, Suit.HEART),
        c(Rank.THREE, Suit.CLUB),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.ROYAL_FLUSH
    assert result.values == (14,)


def test_straight_flush():
    cards = [
        c(Rank.NINE, Suit.HEART),
        c(Rank.EIGHT, Suit.HEART),
        c(Rank.SEVEN, Suit.HEART),
        c(Rank.SIX, Suit.HEART),
        c(Rank.FIVE, Suit.HEART),
        c(Rank.ACE, Suit.CLUB),
        c(Rank.TWO, Suit.DIAMOND),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.STRAIGHT_FLUSH
    assert result.values == (9,)


def test_four_of_a_kind():
    cards = [
        c(Rank.ACE, Suit.SPADE),
        c(Rank.ACE, Suit.HEART),
        c(Rank.ACE, Suit.DIAMOND),
        c(Rank.ACE, Suit.CLUB),
        c(Rank.KING, Suit.SPADE),
        c(Rank.TWO, Suit.HEART),
        c(Rank.THREE, Suit.CLUB),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.FOUR_OF_A_KIND
    assert result.values == (14, 13)


def test_full_house():
    cards = [
        c(Rank.KING, Suit.SPADE),
        c(Rank.KING, Suit.HEART),
        c(Rank.KING, Suit.DIAMOND),
        c(Rank.TWO, Suit.CLUB),
        c(Rank.TWO, Suit.SPADE),
        c(Rank.NINE, Suit.HEART),
        c(Rank.THREE, Suit.CLUB),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.FULL_HOUSE
    assert result.values == (13, 2)


def test_flush():
    cards = [
        c(Rank.ACE, Suit.CLUB),
        c(Rank.JACK, Suit.CLUB),
        c(Rank.NINE, Suit.CLUB),
        c(Rank.SEVEN, Suit.CLUB),
        c(Rank.THREE, Suit.CLUB),
        c(Rank.TWO, Suit.HEART),
        c(Rank.FOUR, Suit.SPADE),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.FLUSH
    assert result.values == (14, 11, 9, 7, 3)


def test_straight_with_ace_low():
    cards = [
        c(Rank.ACE, Suit.SPADE),
        c(Rank.FIVE, Suit.HEART),
        c(Rank.FOUR, Suit.DIAMOND),
        c(Rank.THREE, Suit.CLUB),
        c(Rank.TWO, Suit.SPADE),
        c(Rank.KING, Suit.HEART),
        c(Rank.NINE, Suit.CLUB),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.STRAIGHT
    assert result.values == (5,)


def test_three_of_a_kind():
    cards = [
        c(Rank.QUEEN, Suit.SPADE),
        c(Rank.QUEEN, Suit.HEART),
        c(Rank.QUEEN, Suit.DIAMOND),
        c(Rank.ACE, Suit.CLUB),
        c(Rank.NINE, Suit.SPADE),
        c(Rank.TWO, Suit.HEART),
        c(Rank.THREE, Suit.CLUB),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.THREE_OF_A_KIND
    assert result.values == (12, 14, 9)


def test_two_pair():
    cards = [
        c(Rank.ACE, Suit.SPADE),
        c(Rank.ACE, Suit.HEART),
        c(Rank.KING, Suit.DIAMOND),
        c(Rank.KING, Suit.CLUB),
        c(Rank.QUEEN, Suit.SPADE),
        c(Rank.TWO, Suit.HEART),
        c(Rank.THREE, Suit.CLUB),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.TWO_PAIR
    assert result.values == (14, 13, 12)


def test_one_pair():
    cards = [
        c(Rank.JACK, Suit.SPADE),
        c(Rank.JACK, Suit.HEART),
        c(Rank.ACE, Suit.DIAMOND),
        c(Rank.KING, Suit.CLUB),
        c(Rank.NINE, Suit.SPADE),
        c(Rank.TWO, Suit.HEART),
        c(Rank.THREE, Suit.CLUB),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.ONE_PAIR
    assert result.values == (11, 14, 13, 9)


def test_high_card():
    cards = [
        c(Rank.ACE, Suit.SPADE),
        c(Rank.KING, Suit.HEART),
        c(Rank.NINE, Suit.DIAMOND),
        c(Rank.SEVEN, Suit.CLUB),
        c(Rank.FOUR, Suit.SPADE),
        c(Rank.TWO, Suit.HEART),
        c(Rank.THREE, Suit.CLUB),
    ]

    result = evaluator.evaluate(cards)

    assert result.rank == HandRank.HIGH_CARD
    assert result.values == (14, 13, 9, 7, 4)


def test_hand_result_comparison():
    one_pair = evaluator.evaluate([
        c(Rank.ACE, Suit.SPADE),
        c(Rank.ACE, Suit.HEART),
        c(Rank.KING, Suit.DIAMOND),
        c(Rank.QUEEN, Suit.CLUB),
        c(Rank.NINE, Suit.SPADE),
        c(Rank.TWO, Suit.HEART),
        c(Rank.THREE, Suit.CLUB),
    ])

    two_pair = evaluator.evaluate([
        c(Rank.KING, Suit.SPADE),
        c(Rank.KING, Suit.HEART),
        c(Rank.QUEEN, Suit.DIAMOND),
        c(Rank.QUEEN, Suit.CLUB),
        c(Rank.NINE, Suit.SPADE),
        c(Rank.TWO, Suit.HEART),
        c(Rank.THREE, Suit.CLUB),
    ])

    assert two_pair > one_pair