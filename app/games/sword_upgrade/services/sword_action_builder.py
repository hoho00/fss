from app.games.sword_upgrade.domain.game import SwordUpgradeGame


def build_sword_upgrade_card_actions(game: SwordUpgradeGame) -> list[tuple[str, str]]:
    _ = game
    return [
        ("검 생성하기", "검생성"),
        ("강화", "강화"),
        ("내검", "내검"),
        ("상태", "상태"),
        ("랭킹", "랭킹"),
        ("도움말", "도움말"),
        ("리셋", "리셋"),
        ("♠️ 홀덤", "게임선택 홀덤"),
        ("🎲 주사위", "게임선택 주사위"),
        ("🃏 바보 라이어", "게임선택 바보라이어게임"),
    ]
