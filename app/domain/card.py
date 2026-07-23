"""
Card domain module.

현재는 텍사스 홀덤에서 사용하지만, 향후 블랙잭 등 다른 카드 게임에서도 재사용할 수 있다.
"""

from dataclasses import dataclass
from enum import Enum


class Suit(str, Enum):
    SPADE = "♠️"
    HEART = "♥️"
    DIAMOND = "♦️"
    CLUB = "🍀"


class Rank(str, Enum):
    TWO = "2"
    THREE = "3"
    FOUR = "4"
    FIVE = "5"
    SIX = "6"
    SEVEN = "7"
    EIGHT = "8"
    NINE = "9"
    TEN = "10"
    JACK = "J"
    QUEEN = "Q"
    KING = "K"
    ACE = "A"


@dataclass(frozen=True)
class Card:
    suit: Suit
    rank: Rank

    def __str__(self) -> str:
        return f"[{self.rank.value}{self.suit.value}]"
