from app.domain.game import GamePhase, HoldemGame


def build_holdem_card_actions(game: HoldemGame) -> list[tuple[str, str]]:
    if game.game_over:
        return [
            ("상태", "상태"),
            ("새게임", "새게임"),
            ("리셋", "리셋"),
            ("랭킹", "랭킹"),
            ("전적", "전적"),
        ]

    if game.phase == GamePhase.WAITING:
        return [
            ("참가", "참가"),
            ("시작", "시작"),
            ("상태", "상태"),
            ("랭킹", "랭킹"),
            ("전적", "전적"),
            ("도움말", "도움말"),
            ("리셋", "리셋"),
            ("🎲 주사위", "게임선택 주사위"),
            ("🃏 바보 라이어", "게임선택 바보라이어게임"),
        ]

    if game.phase == GamePhase.FINISHED:
        return [
            ("시작", "시작"),
            ("상태", "상태"),
            ("도움말", "도움말"),
            ("리셋", "리셋"),
        ]

    if game.phase in {
        GamePhase.PRE_FLOP,
        GamePhase.FLOP,
        GamePhase.TURN,
        GamePhase.RIVER,
    }:
        actions = [
            ("상태", "상태"),
            ("내카드", "내카드"),
        ]

        if game.current_turn_index is None:
            return actions

        current_player = game.players[game.current_turn_index]
        need_to_call = game.current_highest_bet - current_player.current_bet

        if need_to_call > 0:
            actions.append((f"콜 +{need_to_call}", "콜"))
        else:
            actions.append(("체크 +0", "체크"))

        actions.extend(
            [
                ("폴드", "폴드"),
                ("올인", "올인"),
            ]
        )

        for raise_increment in [100, 300, 500, 1000]:
            raise_to_amount = game.current_highest_bet + raise_increment
            actions.append(
                (
                    f"레이즈 +{raise_increment}",
                    f"레이즈 {raise_to_amount}",
                )
            )

        return actions

    return [("상태", "상태")]
