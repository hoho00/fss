from app.games.sword_upgrade.domain.game import SwordUpgradeGame
from app.games.sword_upgrade.domain.raid import RaidPhase


def build_sword_upgrade_card_actions(game: SwordUpgradeGame) -> list[tuple[str, str]]:
    actions: list[tuple[str, str]] = []
    if game.raid is not None and game.raid.phase == RaidPhase.INVITING:
        actions.extend(
            [
                ("지금 시작", "레이드지금시작"),
                ("레이드수락", "레이드수락"),
                ("레이드거부", "레이드거부"),
                ("레이드취소", "레이드취소"),
            ]
        )
    elif game.raid is not None and game.raid.phase == RaidPhase.BATTLING:
        actions.extend(
            [
                ("공격", "공격"),
                ("레이드취소", "레이드취소"),
            ]
        )
    else:
        actions.append(("보스레이드", "보스레이드"))

    actions.extend(
        [
            ("내검", "내검"),
            ("상태", "상태"),
            ("랭킹", "랭킹"),
            ("도움말", "도움말"),
        ]
    )
    if not game.is_raid_active():
        actions.append(("리셋", "리셋"))
        actions.extend(
            [
                ("♠️ 홀덤", "게임선택 홀덤"),
                ("🎲 주사위", "게임선택 주사위"),
                ("🃏 바보 라이어", "게임선택 바보라이어게임"),
            ]
        )
    return actions
