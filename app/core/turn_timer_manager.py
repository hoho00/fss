import threading
from collections.abc import Callable
from typing import Any


class TurnTimerManager:
    def __init__(self):
        self.timers: dict[str, Any] = {}
        self.generations: dict[str, int] = {}
        self.lock = threading.RLock()

    def next_generation(self, room_id: str) -> int:
        with self.lock:
            generation = self.generations.get(room_id, 0) + 1
            self.generations[room_id] = generation
            return generation

    def cancel(self, room_id: str) -> None:
        with self.lock:
            self.next_generation(room_id)
            timer = self.timers.pop(room_id, None)
        if timer is not None:
            timer.cancel()

    def refresh(
        self,
        room_id: str,
        timer_builder: Callable[[int], Any | None],
    ) -> None:
        with self.lock:
            old_timer = self.timers.pop(room_id, None)
            generation = self.next_generation(room_id)
            timer = timer_builder(generation)
            if timer is not None:
                self.timers[room_id] = timer

        if old_timer is not None:
            old_timer.cancel()
        if timer is not None:
            timer.start()

    def is_current_generation(self, room_id: str, generation: int) -> bool:
        with self.lock:
            return self.generations.get(room_id) == generation
