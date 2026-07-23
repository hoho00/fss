from app.domain.hand_evaluator import HandRank
from app.domain.player import Player
from app.games.holdem.domain.phase import GamePhase


class HoldemShowdownMixin:
    """쇼다운 판정, 팟 분배, 핸드 종료를 담당한다."""

    def _showdown(self) -> str:
        active_players = self._active_players()
        if len(active_players) == 1:
            return self._finish_by_fold()
        while len(self.community_cards) < 5:
            self._draw_community_cards(1)

        overall_winners, overall_result, _ = self._best_players_with_result(
            active_players
        )
        winner_names = ", ".join(player.display_name for player in overall_winners)
        hand_text = self._hand_result_text(overall_result.rank)
        previous_eliminated_ids = {
            player.get("person_id") for player in self.eliminated_players
        }
        payout_lines = self._payout_showdown_pots()

        self.pot = 0
        self.phase = GamePhase.FINISHED
        self.current_turn_index = None
        self._finish_hand_after_payout()

        new_eliminated_names = [
            player.get("display_name")
            for player in self.eliminated_players
            if player.get("person_id") not in previous_eliminated_ids
        ]
        message_lines = ["쇼다운 결과", "", "공개된 패:"]
        message_lines.extend(self._showdown_player_detail_lines(active_players))
        message_lines.extend(["", f"승자: {winner_names} - {hand_text}"])
        if payout_lines:
            message_lines.extend(["", "팟 정산:", *payout_lines])
        if new_eliminated_names:
            message_lines.extend(["", "탈락: " + ", ".join(new_eliminated_names)])
        if self.game_over and self.final_winner_name:
            message_lines.extend(["", f"최종 우승: {self.final_winner_name}님"])
        return "\n".join(message_lines)

    def _showdown_player_detail_lines(
        self, active_players: list[Player]
    ) -> list[str]:
        lines = []
        for player in active_players:
            result, best_cards = self.hand_evaluator.evaluate_with_cards(
                player.hole_cards + self.community_cards
            )
            lines.append(
                f"- {player.display_name} 홀카드: "
                f"{self._cards_text(player.hole_cards)} / "
                f"{self._hand_result_text(result.rank)} / "
                f"베스트5: {self._cards_text(best_cards)}"
            )
        return lines

    def _payout_showdown_pots(self) -> list[str]:
        contributors = [player for player in self.players if player.total_bet > 0]
        if not contributors:
            return []

        pots = []
        previous_level = 0
        bet_levels = sorted({player.total_bet for player in contributors})
        for level in bet_levels:
            level_contributors = [
                player for player in contributors if player.total_bet >= level
            ]
            pot_amount = (level - previous_level) * len(level_contributors)
            eligible_players = [
                player for player in level_contributors if not player.folded
            ]
            if pot_amount > 0 and eligible_players:
                pots.append(
                    {"amount": pot_amount, "eligible_players": eligible_players}
                )
            previous_level = level

        calculated_pot = sum(pot["amount"] for pot in pots)
        if pots and self.pot > calculated_pot:
            pots[-1]["amount"] += self.pot - calculated_pot

        payout_lines = []
        for index, pot in enumerate(pots):
            pot_amount = pot["amount"]
            winners, _, _ = self._best_players_with_result(
                pot["eligible_players"]
            )
            split_amount, remainder = divmod(pot_amount, len(winners))
            for winner_index, winner in enumerate(winners):
                winner.chips += split_amount + (remainder if winner_index == 0 else 0)

            winner_names = ", ".join(winner.display_name for winner in winners)
            pot_name = "메인팟" if index == 0 else f"사이드팟 {index}"
            payout_lines.append(f"- {pot_name} {pot_amount}칩: {winner_names}")
        return payout_lines

    def _best_players(self, players: list[Player]) -> list[Player]:
        results = [
            (
                player,
                self.hand_evaluator.evaluate(player.hole_cards + self.community_cards),
            )
            for player in players
        ]
        best_result = max(result for _, result in results)
        return [player for player, result in results if result == best_result]

    def _best_players_with_result(self, players: list[Player]):
        results = [
            (
                player,
                *self.hand_evaluator.evaluate_with_cards(
                    player.hole_cards + self.community_cards
                ),
            )
            for player in players
        ]
        best_result = max(result for _, result, _ in results)
        winners = [
            player for player, result, _ in results if result == best_result
        ]
        best_cards_by_player = {
            player.person_id: best_cards for player, _, best_cards in results
        }
        return winners, best_result, best_cards_by_player

    def _hand_result_text(self, hand_rank: HandRank) -> str:
        return {
            HandRank.ROYAL_FLUSH: "로열 플러시",
            HandRank.STRAIGHT_FLUSH: "스트레이트 플러시",
            HandRank.FOUR_OF_A_KIND: "포카드",
            HandRank.FULL_HOUSE: "풀하우스",
            HandRank.FLUSH: "플러시",
            HandRank.STRAIGHT: "스트레이트",
            HandRank.THREE_OF_A_KIND: "트리플",
            HandRank.TWO_PAIR: "투페어",
            HandRank.ONE_PAIR: "원페어",
            HandRank.HIGH_CARD: "하이카드",
        }[hand_rank]

    def _finish_by_fold(self) -> str:
        active_players = self._active_players()
        if not active_players:
            raise ValueError("승리자를 찾을 수 없습니다.")

        winner = active_players[0]
        winner.chips += self.pot
        won_pot = self.pot
        self.pot = 0
        previous_eliminated_ids = {
            player.get("person_id") for player in self.eliminated_players
        }
        self.phase = GamePhase.FINISHED
        self.current_turn_index = None
        self._finish_hand_after_payout()

        new_eliminated_names = [
            player.get("display_name")
            for player in self.eliminated_players
            if player.get("person_id") not in previous_eliminated_ids
        ]
        message_lines = [f"{winner.display_name}님이 팟 {won_pot}칩을 획득했습니다."]
        if new_eliminated_names:
            message_lines.append("탈락: " + ", ".join(new_eliminated_names))
        if self.game_over and self.final_winner_name:
            message_lines.append(f"최종 우승: {self.final_winner_name}님")
        return "\n".join(message_lines)

    def _finish_hand_after_payout(self) -> None:
        already_eliminated_ids = {
            player.get("person_id") for player in self.eliminated_players
        }
        for player in [player for player in self.players if player.chips <= 0]:
            if player.person_id not in already_eliminated_ids:
                self.eliminated_players.append(
                    {
                        "person_id": player.person_id,
                        "display_name": player.display_name,
                        "chips": player.chips,
                    }
                )
                already_eliminated_ids.add(player.person_id)

        players_by_id = {player.person_id: player for player in self.players}
        for person_id in list(self.pending_timeout_exclusion_ids):
            if person_id in self.timeout_excluded_player_ids:
                continue
            player = players_by_id.get(person_id)
            display_name = player.display_name if player else person_id
            chips = player.chips if player else 0
            self.timeout_excluded_player_ids.append(person_id)
            if person_id not in already_eliminated_ids:
                self.eliminated_players.append(
                    {
                        "person_id": person_id,
                        "display_name": display_name,
                        "chips": chips,
                        "reason": "turn_timeout",
                    }
                )

        self.players = [
            player
            for player in self.players
            if player.chips > 0
            and player.person_id not in self.timeout_excluded_player_ids
        ]
        self.pending_timeout_exclusion_ids = [
            person_id
            for person_id in self.pending_timeout_exclusion_ids
            if person_id not in self.timeout_excluded_player_ids
        ]

        if self.players:
            self.dealer_index = (
                0 if self.dealer_index is None else self.dealer_index % len(self.players)
            )
        else:
            self.dealer_index = None

        if len(self.players) == 1:
            self.game_over = True
            self.final_winner_name = self.players[0].display_name
            self.phase = GamePhase.FINISHED
            self.current_turn_index = None
