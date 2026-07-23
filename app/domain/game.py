"""
Holdem game domain module.

현재 이 파일은 FSS의 첫 번째 게임인 텍사스 홀덤의 핵심 게임 로직을 담당한다.

주의:
- FSS는 홀덤 전용 봇이 아니라 멀티게임 플랫폼이다.
- 이 파일은 나중에 app/games/holdem/domain/game.py 로 이동될 예정이다.
- 지금은 홀덤 기능이 안정화된 상태이므로, 대규모 폴더 이동은 하지 않는다.
"""

import uuid

from app.domain.card import Card
from app.domain.deck import Deck
from app.domain.hand_evaluator import HandEvaluator
from app.domain.player import Player
from app.games.holdem.domain.betting import HoldemBettingMixin
from app.games.holdem.domain.phase import GamePhase
from app.games.holdem.domain.showdown import HoldemShowdownMixin
from app.games.holdem.domain.serializer import restore_holdem_game, serialize_holdem_game



class HoldemGame(HoldemBettingMixin, HoldemShowdownMixin):
    def __init__(self):
        self.players: list[Player] = []
        self.deck = Deck()
        self.community_cards: list[Card] = []

        self.phase = GamePhase.WAITING

        self.pot = 0
        self.dealer_index: int | None = None
        self.current_turn_index: int | None = None

        self.small_blind = 100
        self.big_blind = 200
        self.current_highest_bet = 0
        self.min_raise = 100

        self.eliminated_players: list[dict] = []
        self.turn_timeout_counts: dict[str, int] = {}
        self.timeout_excluded_player_ids: list[str] = []
        self.pending_timeout_exclusion_ids: list[str] = []
        self.game_over = False
        self.final_winner_name: str | None = None
        self.game_id: str | None = None

        self.hand_evaluator = HandEvaluator()

    def join(self, person_id: str, display_name: str) -> str:
        if person_id in self.timeout_excluded_player_ids:
            raise ValueError("시간 초과로 제외된 플레이어는 현재 토너먼트에 다시 참가할 수 없습니다.")

        if self._find_player_index(person_id) is not None:
            return f"{display_name}님은 이미 참가 중입니다."

        if self.game_over:
            raise ValueError("게임이 종료되었습니다. 리셋 후 다시 참가해야 합니다.")

        if self.phase != GamePhase.WAITING:
            raise ValueError("게임 시작 후에는 참가할 수 없습니다.")

        self.players.append(
            Player(
                person_id=person_id,
                display_name=display_name,
            )
        )

        return f"{display_name}님이 참가했습니다."

    def start(self) -> str:
        if self.game_over:
            raise ValueError("게임이 종료되었습니다. 리셋 후 다시 시작해야 합니다.")

        if self.phase not in [GamePhase.WAITING, GamePhase.FINISHED]:
            raise ValueError("이미 게임이 진행 중입니다.")

        is_new_hand = self.phase == GamePhase.FINISHED

        self.players = [
            player
            for player in self.players
            if (
                player.chips > 0
                and player.person_id not in self.timeout_excluded_player_ids
                and player.person_id not in self.pending_timeout_exclusion_ids
            )
        ]

        if len(self.players) < 2:
            raise ValueError("게임 시작에는 최소 2명 이상 필요합니다.")

        if self.game_id is None:
            self.game_id = str(uuid.uuid4())

        if self.dealer_index is None:
            self.dealer_index = 0
        elif is_new_hand:
            self.dealer_index = (self.dealer_index + 1) % len(self.players)

        self.phase = GamePhase.PRE_FLOP
        self.deck = Deck()
        self.deck.shuffle()
        self.community_cards = []

        self.pot = 0
        self.current_highest_bet = 0
        self.min_raise = 100
        self.current_turn_index = None

        for player in self.players:
            player.clear_for_new_hand()

        self._deal_hole_cards()
        self._post_blinds()

        if is_new_hand:
            return "새 판을 시작했습니다."

        return "게임을 시작했습니다."

    def can_reset(self) -> bool:
        if self.game_over:
            return True

        return self.phase in [
            GamePhase.WAITING,
            GamePhase.FINISHED,
        ]

    def reset(self) -> str:
        if not self.can_reset():
            raise ValueError(
                "게임 진행 중에는 리셋할 수 없습니다. 현재 판이 끝난 뒤 리셋해주세요."
            )

        self.__init__()

        return "게임을 리셋했습니다."

    def record_turn_timeout(self, person_id: str) -> int:
        timeout_count = self.turn_timeout_counts.get(person_id, 0) + 1
        self.turn_timeout_counts[person_id] = timeout_count

        if timeout_count >= 3:
            if person_id not in self.pending_timeout_exclusion_ids:
                self.pending_timeout_exclusion_ids.append(person_id)

        return timeout_count

    def restart_tournament_with_same_players(self) -> str:
        if not self.game_over:
            raise ValueError("새게임은 최종 우승 후 사용할 수 있습니다.")

        participants: list[tuple[str, str]] = []
        seen_person_ids = set()

        for player in self.players:
            if player.person_id in seen_person_ids:
                continue

            participants.append(
                (
                    player.person_id,
                    player.display_name,
                )
            )
            seen_person_ids.add(player.person_id)

        for eliminated_player in self.eliminated_players:
            person_id = eliminated_player.get("person_id")
            display_name = eliminated_player.get("display_name")

            if not person_id or not display_name:
                continue

            if person_id in seen_person_ids:
                continue

            participants.append(
                (
                    person_id,
                    display_name,
                )
            )
            seen_person_ids.add(person_id)

        if len(participants) < 2:
            raise ValueError("새게임을 시작할 참가자가 부족합니다.")

        self.__init__()

        self.players = [
            Player(
                person_id=person_id,
                display_name=display_name,
                chips=10000,
            )
            for person_id, display_name in participants
        ]

        self.start()

        return "같은 참가자로 새 토너먼트를 시작했습니다."

    def status(self) -> str:
        lines = [
            f"현재 상태: {self.phase.value}",
            f"보드: {self._cards_text(self.community_cards)}",
            f"팟: {self.pot}",
            f"현재 최고 베팅: {self.current_highest_bet}",
            f"최소 레이즈: {self.min_raise}",
            f"딜러: {self._dealer_name()}",
            f"현재 차례: {self._current_turn_name()}",
            "",
            "참가자:",
        ]

        if not self.players:
            lines.append("참가자 없음")
        else:
            for index, player in enumerate(self.players, start=1):
                zero_based_index = index - 1

                position_marker = self._position_marker_for_index(
                    zero_based_index
                )
                position_text = ""

                if position_marker:
                    position_text = f" ({position_marker})"

                state_markers = self._state_markers_for_player(
                    zero_based_index,
                    player,
                )
                state_text = ""

                if state_markers:
                    state_text = ", 상태: " + ", ".join(state_markers)

                player_line = (
                    f"{index}. {player.display_name}{position_text} - "
                    f"{player.chips}칩, "
                    f"현재 베팅 {player.current_bet}, "
                    f"총 베팅 {player.total_bet}"
                    f"{state_text}"
                )

                if zero_based_index == self.current_turn_index:
                    player_line = f"👉 **{player_line}**"

                lines.append(player_line)

        if self.eliminated_players:
            eliminated_names = ", ".join(
                eliminated_player.get("display_name")
                for eliminated_player in self.eliminated_players
            )

            lines.extend(
                [
                    "",
                    f"탈락자: {eliminated_names}",
                ]
            )

        if self.game_over:
            lines.extend(
                [
                    "",
                    f"최종 우승: {self.final_winner_name}님",
                ]
            )

        return "\n".join(lines)

    def private_cards(self, person_id: str) -> str:
        player = self._get_player(person_id)
        return player.private_cards_text()

    def to_dict(self) -> dict:
        return serialize_holdem_game(self)

    @classmethod
    def from_dict(cls, data: dict) -> "HoldemGame":
        game = cls()
        restore_holdem_game(game, data, GamePhase)
        return game

    def _deal_hole_cards(self) -> None:
        for _ in range(2):
            for player in self.players:
                player.receive_card(self.deck.draw())

    def _draw_community_cards(self, count: int) -> None:
        for _ in range(count):
            self.community_cards.append(self.deck.draw())

    def _active_players(self) -> list[Player]:
        return [
            player
            for player in self.players
            if not player.folded
        ]

    def _active_player_count(self) -> int:
        return len(self._active_players())

    def _find_player_index(self, person_id: str) -> int | None:
        for index, player in enumerate(self.players):
            if player.person_id == person_id:
                return index

        return None

    def _get_player(self, person_id: str) -> Player:
        player_index = self._find_player_index(person_id)

        if player_index is None:
            raise ValueError("참가자를 찾을 수 없습니다.")

        return self.players[player_index]

    def _dealer_name(self) -> str:
        if self.dealer_index is None:
            return "없음"

        if not self.players:
            return "없음"

        return self.players[self.dealer_index].display_name

    def _current_turn_name(self) -> str:
        if self.current_turn_index is None:
            return "없음"

        if not self.players:
            return "없음"

        return self.players[self.current_turn_index].display_name

    def _cards_text(self, cards: list[Card]) -> str:
        if not cards:
            return "없음"

        return " ".join(str(card) for card in cards)

    def _position_marker_for_index(self, player_index: int) -> str | None:
        if self.dealer_index is None:
            return None

        blind_marker = self._blind_marker_for_index(player_index)
        is_dealer = player_index == self.dealer_index

        if is_dealer and blind_marker:
            return f"D/{blind_marker}"

        if is_dealer:
            return "D"

        if blind_marker:
            return blind_marker

        return None

    def _state_markers_for_player(
        self,
        player_index: int,
        player: Player,
    ) -> list[str]:
        markers = []

        if player_index == self.current_turn_index:
            markers.append("턴")

        if player.folded:
            markers.append("폴드")

        if player.all_in:
            markers.append("올인")

        return markers

    def _blind_marker_for_index(self, player_index: int) -> str | None:
        if self.dealer_index is None:
            return None

        if self.phase not in [
            GamePhase.PRE_FLOP,
            GamePhase.FLOP,
            GamePhase.TURN,
            GamePhase.RIVER,
        ]:
            return None

        player_count = len(self.players)

        if player_count < 2:
            return None

        if player_count == 2:
            small_blind_index = self.dealer_index
            big_blind_index = (self.dealer_index + 1) % player_count
        else:
            small_blind_index = (self.dealer_index + 1) % player_count
            big_blind_index = (self.dealer_index + 2) % player_count

        if player_index == small_blind_index:
            return "SB"

        if player_index == big_blind_index:
            return "BB"

        return None
