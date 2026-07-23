from app.domain.player import Player
from app.games.holdem.domain.phase import GamePhase


class HoldemBettingMixin:
    """베팅 액션과 베팅 라운드 전환을 담당한다."""

    def call(self, person_id: str) -> str:
        index, player = self._require_action_player(person_id)
        need_to_call = self.current_highest_bet - player.current_bet
        if need_to_call <= 0:
            raise ValueError("콜할 금액이 없습니다. 체크해야 합니다.")

        amount = min(need_to_call, player.chips)
        if amount <= 0:
            raise ValueError("콜할 칩이 없습니다.")

        player.bet(amount)
        player.mark_acted()
        self.pot += amount
        return self._action_message(
            f"{player.display_name}님이 {amount}칩 콜했습니다.", index
        )

    def check(self, person_id: str) -> str:
        index, player = self._require_action_player(person_id)
        if self.current_highest_bet - player.current_bet > 0:
            raise ValueError("체크할 수 없습니다. 콜 또는 폴드해야 합니다.")

        player.mark_acted()
        return self._action_message(f"{player.display_name}님이 체크했습니다.", index)

    def fold(self, person_id: str) -> str:
        index, player = self._require_action_player(person_id)
        player.fold()
        return self._action_message(f"{player.display_name}님이 폴드했습니다.", index)

    def raise_to(self, person_id: str, total_bet_amount: int) -> str:
        index, player = self._require_action_player(person_id)
        if total_bet_amount <= self.current_highest_bet:
            raise ValueError("레이즈 금액은 현재 최고 베팅보다 커야 합니다.")

        additional_amount = total_bet_amount - player.current_bet
        if additional_amount <= 0:
            raise ValueError("레이즈할 금액이 없습니다.")
        if additional_amount > player.chips:
            raise ValueError("보유 칩보다 많이 레이즈할 수 없습니다.")

        raise_size = total_bet_amount - self.current_highest_bet
        if raise_size < self.min_raise and additional_amount != player.chips:
            raise ValueError(f"최소 레이즈 금액은 {self.min_raise}칩입니다.")

        player.bet(additional_amount)
        self.pot += additional_amount
        old_highest_bet = self.current_highest_bet
        self.current_highest_bet = player.current_bet
        if self.current_highest_bet > old_highest_bet:
            self._reset_other_players_acted(player.person_id)
        if raise_size >= self.min_raise:
            self.min_raise = raise_size
        player.mark_acted()

        message = f"{player.display_name}님이 {total_bet_amount}칩으로 레이즈했습니다."
        if player.all_in:
            message = f"{player.display_name}님이 {total_bet_amount}칩으로 올인 레이즈했습니다."
        return self._action_message(message, index)

    def all_in(self, person_id: str) -> str:
        index, player = self._require_action_player(person_id)
        amount = player.chips
        if amount <= 0:
            raise ValueError("올인할 칩이 없습니다.")

        old_highest_bet = self.current_highest_bet
        player.bet(amount)
        player.mark_acted()
        self.pot += amount
        if player.current_bet > self.current_highest_bet:
            raise_size = player.current_bet - old_highest_bet
            self.current_highest_bet = player.current_bet
            if raise_size >= self.min_raise:
                self.min_raise = raise_size
                self._reset_other_players_acted(player.person_id)
            player.mark_acted()

        return self._action_message(
            f"{player.display_name}님이 {amount}칩 올인했습니다.", index
        )

    def _action_message(self, message: str, acted_index: int) -> str:
        finish_message = self._after_action(acted_index)
        return message + "\n" + finish_message if finish_message else message

    def _post_blinds(self) -> None:
        player_count = len(self.players)
        if player_count < 2:
            raise ValueError("블라인드를 낼 플레이어가 부족합니다.")
        assert self.dealer_index is not None

        if player_count == 2:
            small_blind_index = self.dealer_index
            big_blind_index = (self.dealer_index + 1) % player_count
            first_turn_index = self.dealer_index
        else:
            small_blind_index = (self.dealer_index + 1) % player_count
            big_blind_index = (self.dealer_index + 2) % player_count
            first_turn_index = (self.dealer_index + 3) % player_count

        self._post_blind(small_blind_index, self.small_blind)
        self._post_blind(big_blind_index, self.big_blind)
        self.current_highest_bet = max(player.current_bet for player in self.players)
        self.current_turn_index = self._find_next_actionable_index(
            start_index=first_turn_index, include_start=True
        )
        if self.current_turn_index is None:
            self._resolve_round_without_actionable_player()

    def _post_blind(self, player_index: int, blind_amount: int) -> None:
        player = self.players[player_index]
        amount = min(blind_amount, player.chips)
        if amount > 0:
            player.bet(amount)
            self.pot += amount

    def _after_action(self, acted_index: int) -> str | None:
        if self._active_player_count() == 1:
            return self._finish_by_fold()
        if self._is_betting_round_complete():
            if self._should_runout_to_showdown():
                return self._runout_to_showdown()
            return self._advance_street()

        self.current_turn_index = self._find_next_actionable_index(
            start_index=acted_index + 1, include_start=True
        )
        if self.current_turn_index is None:
            return self._resolve_round_without_actionable_player()
        return None

    def _resolve_round_without_actionable_player(self) -> str | None:
        if self._active_player_count() == 1:
            return self._finish_by_fold()
        if self._should_runout_to_showdown():
            return self._runout_to_showdown()
        if self._is_betting_round_complete():
            return self._advance_street()
        raise ValueError("다음 차례를 찾을 수 없습니다.")

    def _is_betting_round_complete(self) -> bool:
        active_players = self._active_players()
        if len(active_players) <= 1:
            return True
        return all(
            player.all_in
            or (player.current_bet >= self.current_highest_bet and player.acted)
            for player in active_players
        )

    def _should_runout_to_showdown(self) -> bool:
        active_players = self._active_players()
        if len(active_players) <= 1:
            return False
        return sum(
            not player.all_in and player.chips > 0 for player in active_players
        ) <= 1

    def _advance_street(self) -> str | None:
        if self.phase == GamePhase.PRE_FLOP:
            self._draw_community_cards(3)
            self.phase = GamePhase.FLOP
            message = f"플랍 오픈: {self._cards_text(self.community_cards)}"
        elif self.phase == GamePhase.FLOP:
            self._draw_community_cards(1)
            self.phase = GamePhase.TURN
            message = f"턴 오픈: {self._cards_text(self.community_cards)}"
        elif self.phase == GamePhase.TURN:
            self._draw_community_cards(1)
            self.phase = GamePhase.RIVER
            message = f"리버 오픈: {self._cards_text(self.community_cards)}"
        elif self.phase == GamePhase.RIVER:
            return self._showdown()
        else:
            return None

        self._reset_bets_for_next_street()
        if self._active_player_count() == 1:
            return self._finish_by_fold()
        if self._should_runout_to_showdown():
            return self._runout_to_showdown()

        assert self.dealer_index is not None
        self.current_turn_index = self._find_next_actionable_index(
            start_index=self.dealer_index + 1, include_start=True
        )
        if self.current_turn_index is None:
            return self._resolve_round_without_actionable_player()
        return message

    def _runout_to_showdown(self) -> str:
        messages = []
        if len(self.community_cards) < 3:
            self._draw_community_cards(3 - len(self.community_cards))
            self.phase = GamePhase.FLOP
            messages.append(f"플랍 오픈: {self._cards_text(self.community_cards)}")
        if len(self.community_cards) == 3:
            self._draw_community_cards(1)
            self.phase = GamePhase.TURN
            messages.append(f"턴 오픈: {self._cards_text(self.community_cards)}")
        if len(self.community_cards) == 4:
            self._draw_community_cards(1)
            self.phase = GamePhase.RIVER
            messages.append(f"리버 오픈: {self._cards_text(self.community_cards)}")
        while len(self.community_cards) < 5:
            self._draw_community_cards(1)
        self.phase = GamePhase.RIVER
        messages.append(self._showdown())
        return "\n".join(messages)

    def _reset_bets_for_next_street(self) -> None:
        for player in self.players:
            player.current_bet = 0
            player.acted = False
        self.current_highest_bet = 0
        self.min_raise = 100

    def _reset_other_players_acted(self, actor_person_id: str) -> None:
        for player in self.players:
            if player.person_id != actor_person_id and not player.folded and not player.all_in:
                player.acted = False

    def _find_next_actionable_index(
        self, start_index: int, include_start: bool
    ) -> int | None:
        if not self.players:
            return None
        player_count = len(self.players)
        offset_start = 0 if include_start else 1
        for offset in range(offset_start, offset_start + player_count):
            index = (start_index + offset) % player_count
            if self._can_player_act(self.players[index]):
                return index
        return None

    def _can_player_act(self, player: Player) -> bool:
        if player.folded or player.all_in or player.chips <= 0:
            return False
        return player.current_bet < self.current_highest_bet or not player.acted

    def _require_action_player(self, person_id: str) -> tuple[int, Player]:
        if self.phase not in {
            GamePhase.PRE_FLOP, GamePhase.FLOP, GamePhase.TURN, GamePhase.RIVER
        }:
            raise ValueError("현재 액션할 수 없는 상태입니다.")
        if self.current_turn_index is None:
            raise ValueError("현재 차례인 플레이어가 없습니다.")

        player_index = self._find_player_index(person_id)
        if player_index != self.current_turn_index:
            current_player = self.players[self.current_turn_index]
            raise ValueError(f"현재 차례는 {current_player.display_name}님입니다.")
        if player_index is None:
            raise ValueError("참가자를 찾을 수 없습니다.")

        player = self.players[player_index]
        if player.folded:
            raise ValueError("이미 폴드한 플레이어입니다.")
        if player.all_in:
            raise ValueError("이미 올인한 플레이어입니다.")
        return player_index, player
