from collections.abc import Callable

from app.core.game_registry import game_type_for_game, plugin_for_type
from app.core.turn_timer_manager import TurnTimerManager


class TurnTimerService:
    def __init__(
        self,
        manager: TurnTimerManager,
        timer_factory: Callable,
        default_timeout_seconds: float,
        get_game: Callable,
        room_ids: Callable[[], list[str]],
        timeout_callback: Callable,
    ):
        self.manager = manager
        self.timer_factory = timer_factory
        self.default_timeout_seconds = default_timeout_seconds
        self.get_game = get_game
        self.room_ids = room_ids
        self.timeout_callback = timeout_callback

    @staticmethod
    def active_actor(game) -> str | None:
        return plugin_for_type(game_type_for_game(game)).active_actor(game)

    @staticmethod
    def should_schedule(game) -> bool:
        return plugin_for_type(game_type_for_game(game)).should_schedule_timer(game)

    def cancel(self, room_id: str) -> None:
        self.manager.cancel(room_id)

    def refresh(self, room_id: str) -> None:
        def build_timer(generation: int):
            game = self.get_game(room_id)
            plugin = plugin_for_type(game_type_for_game(game))
            if not plugin.should_schedule_timer(game):
                return None
            person_id = plugin.active_actor(game)
            seconds = plugin.timer_seconds(game, self.default_timeout_seconds)
            timer = self.timer_factory(
                seconds,
                self.timeout_callback,
                args=(room_id, generation, person_id),
            )
            if hasattr(timer, "daemon"):
                timer.daemon = True
            return timer

        self.manager.refresh(room_id, build_timer)

    def refresh_all(self) -> None:
        for room_id in self.room_ids():
            self.refresh(room_id)

    def is_current(self, room_id: str, generation: int, person_id: str) -> bool:
        if not self.manager.is_current_generation(room_id, generation):
            return False
        game = self.get_game(room_id)
        return self.should_schedule(game) and self.active_actor(game) == person_id
