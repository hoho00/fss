from dataclasses import dataclass, field

from app.domain.card import Card


@dataclass
class Player:
    person_id: str
    display_name: str
    chips: int = 10000
    hole_cards: list[Card] = field(default_factory=list)

    folded: bool = False
    all_in: bool = False
    acted: bool = False

    current_bet: int = 0
    total_bet: int = 0

    def receive_card(self, card: Card) -> None:
        if len(self.hole_cards) >= 2:
            raise ValueError("홀카드는 2장을 초과할 수 없습니다.")

        self.hole_cards.append(card)

    def bet(self, amount: int) -> None:
        if amount <= 0:
            raise ValueError("베팅 금액은 0보다 커야 합니다.")

        if amount > self.chips:
            raise ValueError("보유 칩보다 많이 베팅할 수 없습니다.")

        self.chips -= amount
        self.current_bet += amount
        self.total_bet += amount

        if self.chips == 0:
            self.all_in = True

    def fold(self) -> None:
        self.folded = True
        self.acted = True

    def mark_acted(self) -> None:
        self.acted = True

    def clear_for_new_hand(self) -> None:
        self.hole_cards.clear()
        self.folded = False
        self.all_in = False
        self.acted = False
        self.current_bet = 0
        self.total_bet = 0

    def reset_for_next_street(self) -> None:
        self.current_bet = 0
        self.acted = False

    def private_cards_text(self) -> str:
        if not self.hole_cards:
            return "아직 카드가 없습니다."

        cards = " ".join(str(card) for card in self.hole_cards)
        return f"{self.display_name}님의 카드: {cards}"