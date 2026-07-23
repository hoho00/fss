from dataclasses import dataclass

from app.commands.parser import CommandParser
from app.core.room_manager import RoomManager
from app.core.turn_timer_manager import TurnTimerManager
from app.services.game_store import JsonGameStore
from app.services.stats_store import JsonStatsStore
from app.services.webex_card_builder import WebexCardBuilder


@dataclass
class ApplicationContainer:
    room_manager: RoomManager
    turn_timer_manager: TurnTimerManager
    game_store: JsonGameStore
    stats_store: JsonStatsStore
    command_parser: CommandParser
    webex_card_builder: WebexCardBuilder

    @classmethod
    def create(cls, processed_webhook_id_limit: int = 5000) -> "ApplicationContainer":
        return cls(
            room_manager=RoomManager(processed_id_limit=processed_webhook_id_limit),
            turn_timer_manager=TurnTimerManager(),
            game_store=JsonGameStore(),
            stats_store=JsonStatsStore(),
            command_parser=CommandParser(),
            webex_card_builder=WebexCardBuilder(),
        )
