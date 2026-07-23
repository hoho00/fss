from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Protocol

from app.domain.game import GamePhase, HoldemGame
from app.games.dice.domain.game import DiceGame, DiceGamePhase
from app.games.dice.services.dice_action_builder import build_dice_card_actions
from app.games.dice.services.dice_bot_service import DiceBotService
from app.games.fool_liar.domain.game import FoolLiarGame, FoolLiarPhase
from app.games.fool_liar.services.fool_liar_action_builder import build_fool_liar_card_actions
from app.games.fool_liar.services.fool_liar_bot_service import FoolLiarBotService
from app.games.holdem.services.holdem_action_builder import build_holdem_card_actions
from app.services.holdem_bot_service import HoldemBotService


class GameType(str, Enum):
    HOLDEM = "holdem"
    DICE = "dice"
    FOOL_LIAR = "fool_liar"


GameInstance = HoldemGame | DiceGame | FoolLiarGame


class BotService(Protocol):
    def handle_text_command(
        self,
        person_id: str,
        display_name: str,
        text: str,
    ) -> dict: ...


@dataclass(frozen=True)
class GamePlugin:
    game_type: GameType
    label: str
    game_class: type
    service_factory: Callable[..., BotService]
    action_builder: Callable[[Any], list[tuple[str, str]]]
    can_change: Callable[[Any], bool]
    active_actor: Callable[[Any], str | None]
    should_schedule_timer: Callable[[Any], bool]
    timer_seconds: Callable[[Any, float], float]

    def create_game(self) -> GameInstance:
        return self.game_class()

    def restore_game(self, state: dict) -> GameInstance:
        return self.game_class.from_dict(state)

    def create_service(self, game, command_parser, stats_store, room_id: str):
        return self.service_factory(game, command_parser, stats_store, room_id)

    def build_actions(self, game) -> list[tuple[str, str]]:
        return self.action_builder(game)


def _holdem_service(game, parser, stats_store, room_id):
    return HoldemBotService(game, parser, stats_store, room_id=room_id)


def _dice_service(game, parser, stats_store, room_id):
    return DiceBotService(game, parser, stats_store)


def _fool_liar_service(game, parser, stats_store, room_id):
    return FoolLiarBotService(game, parser, stats_store)


def _holdem_active_actor(game: HoldemGame) -> str | None:
    if game.current_turn_index is None or not game.players:
        return None
    if game.current_turn_index >= len(game.players):
        return None
    return game.players[game.current_turn_index].person_id


def _holdem_should_schedule_timer(game: HoldemGame) -> bool:
    if game.game_over or game.phase not in {
        GamePhase.PRE_FLOP,
        GamePhase.FLOP,
        GamePhase.TURN,
        GamePhase.RIVER,
    }:
        return False
    if game.current_turn_index is None or game.current_turn_index >= len(game.players):
        return False
    player = game.players[game.current_turn_index]
    return not player.folded and not player.all_in and player.chips > 0


GAME_PLUGINS = {
    GameType.HOLDEM: GamePlugin(
        GameType.HOLDEM,
        "홀덤",
        HoldemGame,
        _holdem_service,
        build_holdem_card_actions,
        lambda game: game.can_reset(),
        _holdem_active_actor,
        _holdem_should_schedule_timer,
        lambda game, default: default,
    ),
    GameType.DICE: GamePlugin(
        GameType.DICE,
        "주사위",
        DiceGame,
        _dice_service,
        build_dice_card_actions,
        lambda game: game.phase in {DiceGamePhase.WAITING, DiceGamePhase.FINISHED},
        lambda game: None,
        lambda game: False,
        lambda game, default: default,
    ),
    GameType.FOOL_LIAR: GamePlugin(
        GameType.FOOL_LIAR,
        "바보 라이어게임",
        FoolLiarGame,
        _fool_liar_service,
        build_fool_liar_card_actions,
        lambda game: game.can_change_game(),
        lambda game: game.current_actor_person_id() or f"__{game.phase.value}__",
        lambda game: game.phase in {
            FoolLiarPhase.EXPLAINING,
            FoolLiarPhase.VOTING,
            FoolLiarPhase.REVOTING,
            FoolLiarPhase.ANSWERING,
        } and game.deadline_at is not None,
        lambda game, default: max(0.01, game.remaining_seconds()),
    ),
}

GAME_LABELS = {game_type: plugin.label for game_type, plugin in GAME_PLUGINS.items()}


def plugin_for_type(game_type: GameType) -> GamePlugin:
    return GAME_PLUGINS[game_type]


def game_type_for_game(game: GameInstance) -> GameType:
    for game_type, plugin in GAME_PLUGINS.items():
        if isinstance(game, plugin.game_class):
            return game_type
    raise ValueError(f"등록되지 않은 게임 클래스입니다: {type(game).__name__}")


def game_type_from_selection(value: str) -> GameType | None:
    normalized = value.strip().lower()
    aliases = {
        "홀덤": GameType.HOLDEM,
        "holdem": GameType.HOLDEM,
        "텍사스홀덤": GameType.HOLDEM,
        "주사위": GameType.DICE,
        "주사위게임": GameType.DICE,
        "dice": GameType.DICE,
        "바보라이어게임": GameType.FOOL_LIAR,
        "바보 라이어게임": GameType.FOOL_LIAR,
        "foolliar": GameType.FOOL_LIAR,
        "fool_liar": GameType.FOOL_LIAR,
    }
    return aliases.get(normalized)


def create_game(game_type: GameType) -> GameInstance:
    return plugin_for_type(game_type).create_game()
