import json
import os
import tempfile
import time
import threading
from pathlib import Path

from app.core.game_registry import GameInstance, GameType, plugin_for_type
from app.services.encrypted_json import EncryptedJsonCodec


class JsonGameStore:
    _save_lock = threading.Lock()

    def __init__(
        self,
        file_path: str | None = None,
        encryption_key: str | bytes | None = None,
    ):
        self.file_path = Path(
            file_path or os.getenv("FSS_GAME_STORE_PATH", "data/games.json")
        )
        self._codec = EncryptedJsonCodec(encryption_key)

    def load_all(self) -> dict[str, GameInstance]:
        data = self._load_raw_data()
        rooms_data = data.get("rooms") or {}

        games = {}

        for room_id, room_data in rooms_data.items():
            game_type = self._room_game_type(room_data)
            game_data = room_data.get("state", room_data)

            games[room_id] = plugin_for_type(game_type).restore_game(game_data)

        return games

    def load_game_types(self) -> dict[str, GameType]:
        data = self._load_raw_data()
        rooms_data = data.get("rooms") or {}

        return {
            room_id: self._room_game_type(room_data)
            for room_id, room_data in rooms_data.items()
        }

    def load_card_tokens(self) -> dict[str, str]:
        data = self._load_raw_data()
        tokens = data.get("latest_card_tokens") or {}

        return {
            room_id: token
            for room_id, token in tokens.items()
            if isinstance(room_id, str) and isinstance(token, str)
        }

    def load_processed_webhook_ids(self) -> list[str]:
        data = self._load_raw_data()
        values = data.get("processed_webhook_ids") or []
        return [value for value in values if isinstance(value, str)]

    def save_all(
        self,
        room_games: dict[str, GameInstance],
        latest_card_tokens: dict[str, str] | None = None,
        room_game_types: dict[str, GameType] | None = None,
        processed_webhook_ids: list[str] | None = None,
    ) -> None:
        with self._save_lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            raw_data = {
                "rooms": {
                    room_id: {
                        "game_type": (room_game_types or {}).get(
                            room_id,
                            GameType.HOLDEM,
                        ).value,
                        "state": game.to_dict(),
                    }
                    for room_id, game in room_games.items()
                },
                "latest_card_tokens": latest_card_tokens or {},
                "processed_webhook_ids": processed_webhook_ids or [],
            }

            fd, temp_path = tempfile.mkstemp(
                dir=self.file_path.parent,
                prefix="games_",
                suffix=".tmp",
                text=True,
            )

            temp_path_obj = Path(temp_path)

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                    temp_file.write(self._codec.dumps(raw_data))
                    temp_file.flush()
                    os.fsync(temp_file.fileno())

                self._replace_with_retry(
                    source=temp_path_obj,
                    target=self.file_path,
                )

            finally:
                if temp_path_obj.exists():
                    try:
                        temp_path_obj.unlink()
                    except PermissionError:
                        pass

    def _load_raw_data(self) -> dict:
        if not self.file_path.exists():
            return {}

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                data, was_plaintext = self._codec.loads(file.read())

        except json.JSONDecodeError:
            return {}

        except PermissionError:
            time.sleep(0.05)

            with self.file_path.open("r", encoding="utf-8") as file:
                data, was_plaintext = self._codec.loads(file.read())

        if was_plaintext:
            self._save_raw_data(data)

        return data

    def _save_raw_data(self, raw_data: dict) -> None:
        """Encrypt a successfully loaded legacy plaintext document."""
        self.file_path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_path = tempfile.mkstemp(
            dir=self.file_path.parent,
            prefix="games_migration_",
            suffix=".tmp",
            text=True,
        )
        temp_path_obj = Path(temp_path)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                temp_file.write(self._codec.dumps(raw_data))
                temp_file.flush()
                os.fsync(temp_file.fileno())
            self._replace_with_retry(temp_path_obj, self.file_path)
        finally:
            if temp_path_obj.exists():
                try:
                    temp_path_obj.unlink()
                except PermissionError:
                    pass

    @staticmethod
    def _room_game_type(room_data: dict) -> GameType:
        value = room_data.get("game_type", GameType.HOLDEM.value)

        try:
            return GameType(value)
        except ValueError:
            return GameType.HOLDEM

    def _replace_with_retry(
        self,
        source: Path,
        target: Path,
        retry_count: int = 20,
        sleep_seconds: float = 0.05,
    ) -> None:
        last_error: PermissionError | None = None

        for _ in range(retry_count):
            try:
                os.replace(source, target)
                return

            except PermissionError as error:
                last_error = error
                time.sleep(sleep_seconds)

        if last_error is not None:
            raise last_error


# Backward-compatible alias for older imports.
JsonHoldemGameStore = JsonGameStore
