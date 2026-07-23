import json
import os
import tempfile
import threading
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

from app.domain.game import HoldemGame
from app.games.dice.domain.game import DiceGame
from app.games.dice.services.dice_stats_handler import DiceStatsHandler
from app.games.fool_liar.domain.game import FoolLiarGame
from app.games.fool_liar.services.fool_liar_stats_handler import FoolLiarStatsHandler
from app.games.holdem.services.holdem_stats_handler import HoldemStatsHandler
from app.services.encrypted_json import EncryptedJsonCodec


class JsonStatsStore:
    _save_lock = threading.RLock()

    def __init__(
        self,
        file_path: str | None = None,
        encryption_key: str | bytes | None = None,
    ):
        self.file_path = Path(
            file_path or os.getenv("FSS_STATS_STORE_PATH", "data/stats.json")
        )
        self._codec = EncryptedJsonCodec(encryption_key)
        self._handlers = {
            "holdem": HoldemStatsHandler(),
            "dice": DiceStatsHandler(),
            "fool_liar": FoolLiarStatsHandler(),
        }

    def record_game_over(self, game: HoldemGame) -> None:
        with self._save_lock:
            self._record_game_over_locked(game)

    def _record_game_over_locked(self, game: HoldemGame) -> None:
        data = self._load()
        if self._handlers["holdem"].record(data, game, datetime.now(timezone.utc)):
            self._save(data)

    def ranking_text(self) -> str:
        data = self._load()
        player_records = data.get("players", {})

        if not player_records:
            return "아직 저장된 전적이 없습니다."

        records = []

        for person_id, record in player_records.items():
            games = int(record.get("games", 0))
            if games == 0:
                continue

            wins = int(record.get("wins", 0))
            eliminations = int(record.get("eliminations", 0))
            win_rate = self._win_rate(wins, games)

            records.append(
                {
                    "person_id": person_id,
                    "display_name": record.get("display_name", "알 수 없음"),
                    "games": games,
                    "wins": wins,
                    "eliminations": eliminations,
                    "win_rate": win_rate,
                    "last_played_at": record.get("last_played_at"),
                }
            )

        if not records:
            return "아직 저장된 전적이 없습니다."

        records.sort(
            key=lambda item: (
                item["wins"],
                item["win_rate"],
                item["games"],
                item["last_played_at"] or "",
            ),
            reverse=True,
        )

        lines = ["랭킹"]

        for index, record in enumerate(records, start=1):
            lines.append(
                f"{index}. {record['display_name']} - "
                f"우승 {record['wins']}회 / "
                f"참가 {record['games']}회 / "
                f"탈락 {record['eliminations']}회 / "
                f"승률 {record['win_rate']:.1f}%"
            )

        return "\n".join(lines)

    def reset_ranking(self) -> None:
        self.reset_holdem_ranking()

    def reset_holdem_ranking(self) -> None:
        self._reset_game_stats("holdem")

    def reset_dice_ranking(self) -> None:
        self._reset_game_stats("dice")

    def reset_fool_liar_ranking(self) -> None:
        self._reset_game_stats("fool_liar")

    def record_dice_game(self, game: DiceGame) -> None:
        with self._save_lock:
            self._record_dice_game_locked(game)

    def _record_dice_game_locked(self, game: DiceGame) -> None:
        data = self._load()
        if self._handlers["dice"].record(data, game, datetime.now(timezone.utc)):
            self._save(data)

    def dice_ranking_text(self) -> str:
        data = self._load()
        records = []

        for person_id, record in data.get("players", {}).items():
            dice_record = record.get("dice", {})
            games = int(dice_record.get("games", 0))
            if games == 0:
                continue

            wins = int(dice_record.get("wins", 0))
            records.append(
                {
                    "person_id": person_id,
                    "display_name": record.get("display_name", "알 수 없음"),
                    "games": games,
                    "wins": wins,
                    "losses": int(dice_record.get("losses", 0)),
                    "win_rate": self._win_rate(wins, games),
                    "last_played_at": dice_record.get("last_played_at") or "",
                }
            )

        if not records:
            return "아직 저장된 주사위 전적이 없습니다."

        if not records:
            return "아직 저장된 전적이 없습니다."

        records.sort(
            key=lambda item: (item["wins"], item["win_rate"], item["games"], item["last_played_at"]),
            reverse=True,
        )
        lines = ["주사위 랭킹"]
        for index, record in enumerate(records, start=1):
            lines.append(
                f"{index}. {record['display_name']} - "
                f"우승 {record['wins']}회 / 참가 {record['games']}회 / "
                f"패배 {record['losses']}회 / 승률 {record['win_rate']:.1f}%"
            )
        return "\n".join(lines)

    def dice_player_record_text(self, person_id: str, display_name: str) -> str:
        record = self._load().get("players", {}).get(person_id)
        dice_record = record.get("dice") if record else None

        if not dice_record or int(dice_record.get("games", 0)) == 0:
            return f"{display_name}님의 저장된 주사위 전적이 아직 없습니다."

        games = int(dice_record.get("games", 0))
        wins = int(dice_record.get("wins", 0))
        losses = int(dice_record.get("losses", 0))
        saved_display_name = record.get("display_name") or display_name

        return (
            f"{saved_display_name}님의 주사위 전적\n\n"
            f"참가: {games}회\n"
            f"우승: {wins}회\n"
            f"패배: {losses}회\n"
            f"승률: {self._win_rate(wins, games):.1f}%\n"
            f"최근 플레이: {self._format_korean_datetime(dice_record.get('last_played_at'))}"
        )

    def record_fool_liar_game(self, game: FoolLiarGame) -> None:
        with self._save_lock:
            self._record_fool_liar_game_locked(game)

    def _record_fool_liar_game_locked(self, game: FoolLiarGame) -> None:
        data = self._load()
        if self._handlers["fool_liar"].record(data, game, datetime.now(timezone.utc)):
            self._save(data)

    def fool_liar_ranking_text(self) -> str:
        records = []
        for record in self._load().get("players", {}).values():
            stats = record.get("fool_liar", {})
            games = int(stats.get("games", 0))
            if games:
                wins = int(stats.get("wins", 0))
                records.append((wins, self._win_rate(wins, games), games, record.get("display_name", "알 수 없음"), stats))
        if not records:
            return "아직 저장된 바보 라이어게임 전적이 없습니다."
        records.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        lines = ["바보 라이어게임 랭킹"]
        for index, (wins, win_rate, games, name, stats) in enumerate(records, start=1):
            lines.append(f"{index}. {name} - 승리 {wins}회 / 참가 {games}회 / 패배 {int(stats.get('losses', 0))}회 / 승률 {win_rate:.1f}%")
        return "\n".join(lines)

    def fool_liar_player_record_text(self, person_id: str, display_name: str) -> str:
        record = self._load().get("players", {}).get(person_id)
        stats = record.get("fool_liar") if record else None
        if not stats or int(stats.get("games", 0)) == 0:
            return f"{display_name}님의 저장된 바보 라이어게임 전적이 아직 없습니다."
        games = int(stats.get("games", 0))
        wins = int(stats.get("wins", 0))
        name = record.get("display_name") or display_name
        return (
            f"{name}님의 바보 라이어게임 전적\n\n"
            f"게임: {games}회 / 승리: {wins}회 / 패배: {int(stats.get('losses', 0))}회 / 승률: {self._win_rate(wins, games):.1f}%\n"
            f"바보 역할: {int(stats.get('fool_games', 0))}회 / 바보 승리: {int(stats.get('fool_wins', 0))}회\n"
            f"일반 역할: {int(stats.get('normal_games', 0))}회 / 일반 승리: {int(stats.get('normal_wins', 0))}회\n"
            f"바보로 지목: {int(stats.get('identified_as_fool', 0))}회 / 정답 성공: {int(stats.get('answer_successes', 0))}회\n"
            f"최근 플레이: {self._format_korean_datetime(stats.get('last_played_at'))}"
        )

    def overall_ranking_text(self) -> str:
        records = []
        for record in self._load().get("players", {}).values():
            dice = record.get("dice", {})
            fool_liar = record.get("fool_liar", {})
            games = int(record.get("games", 0)) + int(dice.get("games", 0)) + int(fool_liar.get("games", 0))
            if games == 0:
                continue
            wins = int(record.get("wins", 0)) + int(dice.get("wins", 0)) + int(fool_liar.get("wins", 0))
            losses = int(record.get("eliminations", 0)) + int(dice.get("losses", 0)) + int(fool_liar.get("losses", 0))
            records.append((wins, self._win_rate(wins, games), games, losses, record.get("display_name", "알 수 없음")))
        if not records:
            return "아직 저장된 전체 전적이 없습니다."
        records.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        lines = ["전체 게임 통합 랭킹"]
        for index, (wins, win_rate, games, losses, name) in enumerate(records, start=1):
            lines.append(f"{index}. {name} - 승리 {wins}회 / 참가 {games}회 / 패배 {losses}회 / 승률 {win_rate:.1f}%")
        return "\n".join(lines)

    def player_record_text(
        self,
        person_id: str,
        display_name: str,
    ) -> str:
        data = self._load()
        player_records = data.get("players", {})
        record = player_records.get(person_id)

        if record is None:
            return f"{display_name}님의 저장된 전적이 아직 없습니다."

        games = int(record.get("games", 0))
        if games == 0:
            return f"{display_name}님의 저장된 홀덤 전적은 아직 없습니다."
        wins = int(record.get("wins", 0))
        eliminations = int(record.get("eliminations", 0))
        win_rate = self._win_rate(wins, games)
        last_played_at = self._format_korean_datetime(
            record.get("last_played_at")
        )

        saved_display_name = record.get("display_name") or display_name

        return (
            f"{saved_display_name}님의 전적\n\n"
            f"참가: {games}회\n"
            f"최종 우승: {wins}회\n"
            f"탈락: {eliminations}회\n"
            f"승률: {win_rate:.1f}%\n"
            f"최근 플레이: {last_played_at}"
        )

    def _win_rate(
        self,
        wins: int,
        games: int,
    ) -> float:
        if games <= 0:
            return 0.0

        return wins / games * 100

    def _reset_game_stats(self, game_type: str) -> None:
        with self._save_lock:
            self._reset_game_stats_locked(game_type)

    def _reset_game_stats_locked(self, game_type: str) -> None:
        data = self._load()
        player_records = data.get("players", {})

        for person_id, record in list(player_records.items()):
            if game_type in {"dice", "fool_liar"}:
                if game_type == "fool_liar":
                    record.pop("fool_liar", None)
                else:
                    record.pop("dice", None)
            else:
                for field in ["games", "wins", "eliminations", "last_played_at"]:
                    record.pop(field, None)

            if not record.get("dice") and not record.get("fool_liar") and int(record.get("games", 0)) == 0:
                player_records.pop(person_id)

        data.setdefault("recorded_game_ids", {}).pop(game_type, None)

        self._save(data)

    def _format_korean_datetime(self, value: str | None) -> str:
        if not value:
            return "-"

        try:
            parsed_datetime = datetime.fromisoformat(value)
        except ValueError:
            return value

        if parsed_datetime.tzinfo is None:
            parsed_datetime = parsed_datetime.replace(tzinfo=timezone.utc)

        korean_timezone = timezone(timedelta(hours=9))
        korean_datetime = parsed_datetime.astimezone(korean_timezone)

        return korean_datetime.strftime("%Y-%m-%d %H:%M")

    def _load(self) -> dict:
        if not self.file_path.exists():
            return {
                "players": {},
            }

        try:
            with self.file_path.open("r", encoding="utf-8") as file:
                data, was_plaintext = self._codec.loads(file.read())

        except json.JSONDecodeError:
            return {
                "players": {},
            }

        except PermissionError:
            time.sleep(0.05)

            with self.file_path.open("r", encoding="utf-8") as file:
                data, was_plaintext = self._codec.loads(file.read())

        if not isinstance(data, dict):
            return {
                "players": {},
            }

        data.setdefault("players", {})

        if was_plaintext:
            self._save(data)

        return data

    def _save(self, data: dict) -> None:
        with self._save_lock:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)

            fd, temp_path = tempfile.mkstemp(
                dir=self.file_path.parent,
                prefix="stats_",
                suffix=".tmp",
                text=True,
            )

            temp_path_obj = Path(temp_path)

            try:
                with os.fdopen(fd, "w", encoding="utf-8") as temp_file:
                    temp_file.write(self._codec.dumps(data))
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
