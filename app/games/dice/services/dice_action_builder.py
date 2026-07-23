from app.games.dice.domain.game import DiceGame, DiceGamePhase


def build_dice_card_actions(game: DiceGame) -> list[tuple[str, str]]:
    if game.phase == DiceGamePhase.FINISHED:
        return [
            ("새게임", "새게임"),
            ("상태", "상태"),
            ("랭킹", "랭킹"),
            ("전적", "전적"),
            ("리셋", "리셋"),
        ]

    return [
        ("참가", "참가"),
        ("시작", "시작"),
        ("상태", "상태"),
        ("랭킹", "랭킹"),
        ("전적", "전적"),
        ("도움말", "도움말"),
        ("리셋", "리셋"),
        ("♠️ 홀덤", "게임선택 홀덤"),
        ("🃏 바보 라이어", "게임선택 바보라이어게임"),
    ]
