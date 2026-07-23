"""
Poker hand evaluator.

현재 텍사스 홀덤 쇼다운에서 7장 중 최선의 5장 족보를 평가하는 데 사용한다.

향후 app/games/holdem/domain/hand_evaluator.py 로 이동될 예정이다.
"""

from dataclasses import dataclass
from enum import IntEnum
from itertools import combinations
from collections import Counter

from app.domain.card import Card, Rank


class HandRank(IntEnum):
    HIGH_CARD = 1
    ONE_PAIR = 2
    TWO_PAIR = 3
    THREE_OF_A_KIND = 4
    STRAIGHT = 5
    FLUSH = 6
    FULL_HOUSE = 7
    FOUR_OF_A_KIND = 8
    STRAIGHT_FLUSH = 9
    ROYAL_FLUSH = 10


@dataclass(frozen=True)
class HandResult:
    rank: HandRank
    values: tuple[int, ...]

    def __lt__(self, other: "HandResult") -> bool:
        return (self.rank, self.values) < (other.rank, other.values)


class HandEvaluator:
    def evaluate(self, cards: list[Card]) -> HandResult:
        result, best_cards = self.evaluate_with_cards(cards)
        return result

    def evaluate_with_cards(self, cards: list[Card]) -> tuple[HandResult, list[Card]]:
        if len(cards) != 7:
            raise ValueError("홀덤 족보 평가는 7장이 필요합니다.")

        best_result: HandResult | None = None
        best_cards: list[Card] = []

        for five_cards_tuple in combinations(cards, 5):
            five_cards = list(five_cards_tuple)
            result = self._evaluate_five(five_cards)

            if best_result is None or best_result < result:
                best_result = result
                best_cards = five_cards

        assert best_result is not None

        return best_result, best_cards

    def _evaluate_five(self, cards: list[Card]) -> HandResult:
        values = self._values_desc(cards)
        counts = Counter(values)

        flush = self._is_flush(cards)
        straight_high = self._straight_high(values)

        if flush and straight_high == 14:
            return HandResult(HandRank.ROYAL_FLUSH, (14,))

        if flush and straight_high is not None:
            return HandResult(HandRank.STRAIGHT_FLUSH, (straight_high,))

        four_value = self._find_rank_by_count(counts, 4)

        if four_value is not None:
            kicker = max(
                value
                for value in values
                if value != four_value
            )
            return HandResult(HandRank.FOUR_OF_A_KIND, (four_value, kicker))

        three_values = self._find_ranks_by_count(counts, 3)
        pair_values = self._find_ranks_by_count(counts, 2)

        if three_values and pair_values:
            return HandResult(
                HandRank.FULL_HOUSE,
                (three_values[0], pair_values[0]),
            )

        if flush:
            return HandResult(HandRank.FLUSH, tuple(values))

        if straight_high is not None:
            return HandResult(HandRank.STRAIGHT, (straight_high,))

        if three_values:
            three_value = three_values[0]
            kickers = [
                value
                for value in values
                if value != three_value
            ]
            return HandResult(
                HandRank.THREE_OF_A_KIND,
                (three_value, *kickers),
            )

        if len(pair_values) >= 2:
            high_pair = pair_values[0]
            low_pair = pair_values[1]
            kicker = max(
                value
                for value in values
                if value != high_pair and value != low_pair
            )
            return HandResult(
                HandRank.TWO_PAIR,
                (high_pair, low_pair, kicker),
            )

        if len(pair_values) == 1:
            pair_value = pair_values[0]
            kickers = [
                value
                for value in values
                if value != pair_value
            ]
            return HandResult(
                HandRank.ONE_PAIR,
                (pair_value, *kickers),
            )

        return HandResult(HandRank.HIGH_CARD, tuple(values))

    def _values_desc(self, cards: list[Card]) -> list[int]:
        return sorted(
            [
                self._rank_value(card.rank)
                for card in cards
            ],
            reverse=True,
        )

    def _rank_value(self, rank: Rank) -> int:
        rank_values = {
            Rank.TWO: 2,
            Rank.THREE: 3,
            Rank.FOUR: 4,
            Rank.FIVE: 5,
            Rank.SIX: 6,
            Rank.SEVEN: 7,
            Rank.EIGHT: 8,
            Rank.NINE: 9,
            Rank.TEN: 10,
            Rank.JACK: 11,
            Rank.QUEEN: 12,
            Rank.KING: 13,
            Rank.ACE: 14,
        }

        return rank_values[rank]

    def _is_flush(self, cards: list[Card]) -> bool:
        first_suit = cards[0].suit
        return all(
            card.suit == first_suit
            for card in cards
        )

    def _straight_high(self, values: list[int]) -> int | None:
        unique_values = sorted(set(values), reverse=True)

        if len(unique_values) < 5:
            return None

        if unique_values == [14, 5, 4, 3, 2]:
            return 5

        for index in range(len(unique_values) - 4):
            window = unique_values[index:index + 5]

            if window[0] - window[4] == 4:
                return window[0]

        return None

    def _find_rank_by_count(
        self,
        counts: Counter[int],
        target_count: int,
    ) -> int | None:
        values = [
            value
            for value, count in counts.items()
            if count == target_count
        ]

        if not values:
            return None

        return max(values)

    def _find_ranks_by_count(
        self,
        counts: Counter[int],
        target_count: int,
    ) -> list[int]:
        return sorted(
            [
                value
                for value, count in counts.items()
                if count == target_count
            ],
            reverse=True,
        )