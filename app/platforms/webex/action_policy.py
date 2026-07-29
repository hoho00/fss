from app.domain.game import GamePhase, HoldemGame
from app.games.dice.domain.game import DiceGame, DiceGamePhase
from app.games.fool_liar.domain.game import FoolLiarGame, FoolLiarPhase
from app.games.sword_upgrade.domain.game import SwordUpgradeGame


def is_turn_action(command_text: str) -> bool:
    normalized = command_text.strip().lower()
    for prefix in ("@fss", "fss"):
        if normalized.startswith(prefix + " "):
            normalized = normalized[len(prefix) :].strip()
            break
    return normalized in {"콜", "체크", "폴드", "올인"} or normalized.startswith(
        "레이즈 "
    )


def is_out_of_turn_result(result: dict) -> bool:
    return result.get("ok") is False and str(result.get("message", "")).startswith(
        "현재 차례는 "
    )


def should_silently_ignore(command_text: str, result: dict) -> bool:
    return is_turn_action(command_text) and is_out_of_turn_result(result)


def can_accept_stale_action(game, command_text: str) -> bool:
    if isinstance(game, FoolLiarGame):
        if command_text in {"상태", "제시어", "도움말"}:
            return True
        return command_text in {"참가", "참가취소", "랭킹", "전적"} and game.phase == FoolLiarPhase.WAITING
    if isinstance(game, DiceGame):
        return command_text in {"상태", "참가"} and game.phase == DiceGamePhase.WAITING
    if isinstance(game, SwordUpgradeGame):
        return command_text in {
            "상태",
            "내검",
            "도움말",
            "랭킹",
            "레이드수락",
            "레이드거부",
            "레이드지금시작",
            "공격",
            "레이드취소",
            "보스레이드",
        }
    if not isinstance(game, HoldemGame):
        return False
    if command_text in {"상태", "내카드", "도움말"}:
        return True
    if command_text in {"참가", "랭킹", "전적"}:
        return game.phase == GamePhase.WAITING and not game.game_over
    return False
