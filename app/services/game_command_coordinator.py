from collections.abc import Callable

from app.commands.parser import CommandParser
from app.core.game_registry import GameInstance, GameType, plugin_for_type
from app.domain.game import GamePhase, HoldemGame
from app.games.dice.domain.game import DiceGame
from app.games.fool_liar.domain.game import FoolLiarGame, FoolLiarPhase
from app.games.mahjong_efficiency.battle_service import BATTLE_HELP
from app.games.sword_upgrade.domain.game import SwordUpgradeGame
from app.platforms.base import PlatformGateway


class GameCommandCoordinator:
    def __init__(
        self,
        command_parser: CommandParser,
        stats_store,
        get_game: Callable[[str], GameInstance],
        get_game_type: Callable[[str], GameType],
        save_state: Callable[[], None],
        refresh_timer: Callable[[str], None],
        should_refresh_timer: Callable[[str, dict], bool],
        debug_room_id: str = "debug-room",
    ):
        self.command_parser = command_parser
        self.stats_store = stats_store
        self.get_game = get_game
        self.get_game_type = get_game_type
        self.save_state = save_state
        self.refresh_timer = refresh_timer
        self.should_refresh_timer = should_refresh_timer
        self.debug_room_id = debug_room_id

    def service_for_room(self, room_id: str):
        game = self.get_game(room_id)
        stats_store = None if room_id == self.debug_room_id else self.stats_store
        return plugin_for_type(self.get_game_type(room_id)).create_service(
            game,
            self.command_parser,
            stats_store,
            room_id,
        )

    def execute(
        self,
        gateway: PlatformGateway,
        room_id: str,
        person_id: str,
        display_name: str,
        text: str,
    ) -> dict:
        game = self.get_game(room_id)
        snapshot = game.to_dict() if isinstance(game, HoldemGame) else None
        result = self.preflight_start(gateway, game, text)
        if result is None:
            result = self.service_for_room(room_id).handle_text_command(
                person_id=person_id,
                display_name=display_name,
                text=text,
            )
        if result.get("deal_private_cards") and snapshot is not None:
            result["_start_snapshot"] = snapshot
        if self.command_parser.normalize(text) in {"도움말", "도움", "명령어", "help"}:
            result["message"] = f"{result.get('message', '')}\n\n{BATTLE_HELP}".strip()
        self.dispatch_direct_messages(gateway, result, self.get_game(room_id))
        self.save_state()
        if self.should_refresh_timer(text, result):
            self.refresh_timer(room_id)
        return result

    def preflight_start(
        self,
        gateway: PlatformGateway,
        game: GameInstance,
        command_text: str,
    ) -> dict | None:
        try:
            is_start = self.command_parser.parse(command_text).type.value == "START"
        except ValueError:
            return None
        if not is_start or isinstance(game, (DiceGame, SwordUpgradeGame)):
            return None

        if isinstance(game, FoolLiarGame):
            if game.phase != FoolLiarPhase.WAITING or len(game.players) < game.MIN_PLAYERS:
                return None
            players = game.players
        else:
            if game.phase not in {GamePhase.WAITING, GamePhase.FINISHED}:
                return None
            players = [
                player
                for player in game.players
                if player.chips > 0
                and player.person_id not in game.timeout_excluded_player_ids
                and player.person_id not in game.pending_timeout_exclusion_ids
            ]
            if len(players) < 2:
                return None

        failures = []
        for player in players:
            try:
                gateway.send_direct_message(
                    person_id=player.person_id,
                    markdown="FSS 게임 개인 메시지 전송 확인이 완료되었습니다.",
                )
            except Exception:
                failures.append(player.display_name)
        if not failures:
            return None
        return {
            "ok": False,
            "message": (
                "개인 메시지를 전송할 수 없어 게임을 시작하지 않았습니다: "
                + ", ".join(dict.fromkeys(failures))
            ),
            "status": game.status(),
        }

    @staticmethod
    def dispatch_direct_messages(
        gateway: PlatformGateway,
        result: dict,
        game: GameInstance | None = None,
    ) -> None:
        direct_messages = result.pop("direct_messages", [])
        failures = []
        for item in direct_messages:
            try:
                gateway.send_direct_message(
                    person_id=item["person_id"],
                    markdown=item["message"],
                    card=item.get("card"),
                )
            except Exception:
                failures.append(item["person_id"])
        if not failures:
            return

        failures = list(dict.fromkeys(failures))
        failed_names = failures
        if isinstance(game, FoolLiarGame):
            failed_names = [game._player_name(person_id) for person_id in failures]
            if result.get("abort_on_dm_failure"):
                game.rollback_start()
        if not result.get("abort_on_dm_failure"):
            result["message"] = (
                f"{result.get('message', '')}\n\n"
                f"개인 메시지 전송 실패: {', '.join(failed_names)}"
            ).strip()
            return
        result.clear()
        result.update(
            {
                "ok": False,
                "message": (
                    "개인 메시지를 전송할 수 없어 게임을 시작하지 않았습니다: "
                    + ", ".join(failed_names)
                ),
                "status": game.status() if game is not None else "",
            }
        )


def should_refresh_timer_after_command(
    command_parser: CommandParser,
    command_text: str,
    result: dict,
) -> bool:
    if result.get("ok") is not True:
        return False
    normalized = command_parser.normalize(command_text)
    if normalized in {"콜", "체크", "폴드", "올인"} or normalized.startswith("레이즈 "):
        return True
    if normalized.startswith(("설명 ", "투표 ", "정답 ")):
        return True
    return normalized in {"시작", "새게임", "리셋", "종료"}
