import random

from app.domain.card import Card, Rank, Suit


class Deck:
    def __init__(self):
        self.cards: list[Card] = [
            Card(suit=suit, rank=rank)
            for suit in Suit
            for rank in Rank
        ]

    def shuffle(self) -> None:
        random.SystemRandom().shuffle(self.cards)

    def draw(self) -> Card:
        if not self.cards:
            raise ValueError("덱에 카드가 없습니다.")

        return self.cards.pop()

    def remaining_count(self) -> int:
        return len(self.cards)