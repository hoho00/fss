from collections.abc import Callable

from app.commands.parser import CommandParser
from app.core.game_registry import (
    GAME_LABELS,
    GameInstance,
    GameType,
    game_type_for_game,
    game_type_from_selection,
    plugin_for_type,
)


class AdminCommandService:
    def __init__(
        self,
        command_parser: CommandParser,
        admin_email: str,
        stats_store,
        get_game: Callable[[str], GameInstance],
        get_game_type: Callable[[str], GameType],
        replace_game: Callable[[str, GameType], GameInstance],
        cancel_timer: Callable[[str], None],
        clear_card_token: Callable[[str], None],
        save_state: Callable[[], None],
        force_reset_admin_person_ids: tuple[str, ...] = (),
        clear_mahjong_battle: Callable[[str], bool] | None = None,
    ):
        self.command_parser = command_parser
        self.admin_email = admin_email.strip().lower()
        self.force_reset_admin_person_ids = {
            person_id.strip()
            for person_id in force_reset_admin_person_ids
            if person_id.strip()
        }
        self.stats_store = stats_store
        self.get_game = get_game
        self.get_game_type = get_game_type
        self.replace_game = replace_game
        self.cancel_timer = cancel_timer
        self.clear_card_token = clear_card_token
        self.save_state = save_state
        self.clear_mahjong_battle = clear_mahjong_battle

    def is_force_reset(self, text: str) -> bool:
        return self.command_parser.normalize(text) == "강제리셋"

    def is_ranking_reset(self, text: str) -> bool:
        return self.command_parser.normalize(text) == "랭킹리셋"

    def is_game_selection(self, text: str) -> bool:
        return self.command_parser.normalize(text).startswith("게임선택 ")

    def selection_from_command(self, text: str) -> GameType | None:
        normalized = self.command_parser.normalize(text)
        prefix = "게임선택 "
        return (
            game_type_from_selection(normalized[len(prefix) :])
            if normalized.startswith(prefix)
            else None
        )

    def is_admin(self, email: str | None) -> bool:
        return bool(email and email.strip().lower() == self.admin_email)

    def is_force_reset_admin(self, person_id: str | None) -> bool:
        """Authorize privileged mutations using the immutable Webex personId."""
        return bool(person_id and person_id.strip() in self.force_reset_admin_person_ids)

    def force_reset(self, room_id: str) -> dict:
        self.cancel_timer(room_id)
        self.replace_game(room_id, self.get_game_type(room_id))
        self.clear_card_token(room_id)
        battle_cleared = False
        if self.clear_mahjong_battle is not None:
            battle_cleared = bool(self.clear_mahjong_battle(room_id))
        self.save_state()
        game = self.get_game(room_id)
        message = "관리자 강제리셋으로 현재 방의 게임을 초기화했습니다."
        if battle_cleared:
            message += " 패효율 대결 상태도 삭제했습니다."
        return {
            "ok": True,
            "message": message,
            "status": game.status(),
        }

    def handle_force_reset(self, room_id: str, person_id: str | None) -> dict:
        if not self.is_force_reset_admin(person_id):
            return {
                "ok": False,
                "message": "권한이 없습니다. 관리자만 강제리셋을 실행할 수 있습니다.",
                "status": self.get_game(room_id).status(),
            }
        return self.force_reset(room_id)

    def select_game(self, room_id: str, text: str) -> dict:
        game_type = self.selection_from_command(text)
        current_game = self.get_game(room_id)
        if game_type is None:
            return {
                "ok": False,
                "message": "게임선택은 홀덤, 주사위, 바보 라이어게임 또는 검키우기만 가능합니다.",
                "status": current_game.status(),
            }
        plugin = plugin_for_type(game_type_for_game(current_game))
        if not plugin.can_change(current_game):
            return {
                "ok": False,
                "message": "게임 진행 중에는 게임을 선택할 수 없습니다. 리셋 후 다시 시도해주세요.",
                "status": current_game.status(),
            }
        self.cancel_timer(room_id)
        selected = self.replace_game(room_id, game_type)
        self.clear_card_token(room_id)
        self.save_state()
        hint = "참가 후 시작해주세요."
        if game_type == GameType.SWORD_UPGRADE:
            hint = "채팅으로 `@FSS 강화` / 보스레이드는 `@FSS 보스레이드`"
        return {
            "ok": True,
            "message": f"{GAME_LABELS[game_type]} 게임을 선택했습니다. {hint}",
            "status": selected.status(),
        }

    def reset_ranking(self, room_id: str, email: str | None) -> dict:
        if not self.is_admin(email):
            return {
                "ok": False,
                "message": "권한이 없습니다. 관리자만 랭킹리셋을 실행할 수 있습니다.",
                "status": self.get_game(room_id).status(),
            }
        game_type = self.get_game_type(room_id)
        resetters = {
            GameType.HOLDEM: self.stats_store.reset_holdem_ranking,
            GameType.DICE: self.stats_store.reset_dice_ranking,
            GameType.FOOL_LIAR: self.stats_store.reset_fool_liar_ranking,
            GameType.SWORD_UPGRADE: lambda: None,
        }
        resetters[game_type]()
        return {
            "ok": True,
            "message": f"관리자가 {GAME_LABELS[game_type]} 랭킹과 전적을 초기화했습니다.",
            "status": self.get_game(room_id).status(),
        }
