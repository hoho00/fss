import threading
from dataclasses import dataclass, field

from app.core.game_registry import GameInstance, GameType, create_game


@dataclass
class RoomManager:
    processed_id_limit: int = 5000
    games: dict[str, GameInstance] = field(default_factory=dict)
    game_types: dict[str, GameType] = field(default_factory=dict)
    card_tokens: dict[str, str] = field(default_factory=dict)
    processed_webhook_ids: list[str] = field(default_factory=list)
    room_locks: dict[str, threading.RLock] = field(default_factory=dict)
    _room_locks_guard: threading.Lock = field(default_factory=threading.Lock)
    _processed_ids_lock: threading.RLock = field(default_factory=threading.RLock)

    def restore(
        self,
        games: dict[str, GameInstance],
        game_types: dict[str, GameType],
        card_tokens: dict[str, str],
        processed_webhook_ids: list[str],
    ) -> None:
        self.games.update(games)
        self.game_types.update(game_types)
        self.card_tokens.update(card_tokens)
        with self._processed_ids_lock:
            self.processed_webhook_ids.extend(
                processed_webhook_ids[-self.processed_id_limit :]
            )

    def get_or_create_game(self, room_id: str) -> tuple[GameInstance, bool]:
        if room_id in self.games:
            return self.games[room_id], False
        game_type = self.game_types.setdefault(room_id, GameType.HOLDEM)
        game = create_game(game_type)
        self.games[room_id] = game
        return game, True

    def game_type(self, room_id: str) -> GameType:
        self.get_or_create_game(room_id)
        return self.game_types.get(room_id, GameType.HOLDEM)

    def replace_game(self, room_id: str, game_type: GameType) -> GameInstance:
        game = create_game(game_type)
        self.game_types[room_id] = game_type
        self.games[room_id] = game
        self.card_tokens.pop(room_id, None)
        return game

    def set_game(
        self,
        room_id: str,
        game: GameInstance,
        game_type: GameType,
    ) -> None:
        self.games[room_id] = game
        self.game_types[room_id] = game_type

    def room_lock(self, room_id: str) -> threading.RLock:
        with self._room_locks_guard:
            return self.room_locks.setdefault(room_id, threading.RLock())

    def is_webhook_processed(self, event_id: str) -> bool:
        with self._processed_ids_lock:
            return event_id in self.processed_webhook_ids

    def mark_webhook_processed(self, event_id: str) -> None:
        with self._processed_ids_lock:
            if event_id in self.processed_webhook_ids:
                return
            self.processed_webhook_ids.append(event_id)
            overflow = len(self.processed_webhook_ids) - self.processed_id_limit
            if overflow > 0:
                del self.processed_webhook_ids[:overflow]
