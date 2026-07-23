import random
import uuid
from dataclasses import dataclass
from enum import Enum


class DiceGamePhase(str, Enum):
    WAITING = "WAITING"
    FINISHED = "FINISHED"


@dataclass
class DicePlayer:
    person_id: str
    display_name: str


class DiceGame:
    def __init__(self):
        self.players: list[DicePlayer] = []
        self.phase = DiceGamePhase.WAITING
        self.last_rolls: dict[str, int] = {}
        self.winner_person_ids: list[str] = []
        self.game_id: str | None = None

    @property
    def game_over(self) -> bool:
        return self.phase == DiceGamePhase.FINISHED

    def join(self, person_id: str, display_name: str) -> str:
        if self.phase != DiceGamePhase.WAITING:
            raise ValueError("게임이 끝난 뒤 새게임을 시작해주세요.")

        if any(player.person_id == person_id for player in self.players):
            raise ValueError("이미 참가했습니다.")

        self.players.append(DicePlayer(person_id, display_name))
        return f"{display_name}님이 주사위 게임에 참가했습니다. ({len(self.players)}명)"

    def start(self) -> str:
        if len(self.players) < 2:
            raise ValueError("주사위 게임은 2명 이상 참가해야 시작할 수 있습니다.")

        if self.phase == DiceGamePhase.FINISHED:
            self.last_rolls = {}
            self.winner_person_ids = []

        self.game_id = str(uuid.uuid4())

        self.phase = DiceGamePhase.FINISHED
        self.last_rolls = {
            player.person_id: random.randint(1, 6)
            for player in self.players
        }
        highest_roll = max(self.last_rolls.values())
        self.winner_person_ids = [
            person_id
            for person_id, roll in self.last_rolls.items()
            if roll == highest_roll
        ]

        rolls = " / ".join(
            f"{player.display_name}: {self.last_rolls[player.person_id]}"
            for player in self.players
        )
        winners = ", ".join(
            player.display_name
            for player in self.players
            if player.person_id in self.winner_person_ids
        )
        winner_label = "공동 우승" if len(self.winner_person_ids) > 1 else "우승"
        return f"주사위 결과\n{rolls}\n\n{winner_label}: {winners} ({highest_roll})"

    def reset(self) -> str:
        self.players = []
        self.phase = DiceGamePhase.WAITING
        self.last_rolls = {}
        self.winner_person_ids = []
        self.game_id = None
        return "주사위 게임을 리셋했습니다."

    def status(self) -> str:
        if not self.players:
            return "주사위 게임 대기 중입니다. 참가 후 시작해주세요."

        player_names = ", ".join(player.display_name for player in self.players)
        if self.phase == DiceGamePhase.WAITING:
            return f"주사위 게임 대기 중 ({len(self.players)}명): {player_names}"

        return f"주사위 게임 종료 ({len(self.players)}명): {player_names}"

    def to_dict(self) -> dict:
        return {
            "players": [player.__dict__ for player in self.players],
            "phase": self.phase.value,
            "last_rolls": self.last_rolls,
            "winner_person_ids": self.winner_person_ids,
            "game_id": self.game_id,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "DiceGame":
        game = cls()
        game.players = [DicePlayer(**player) for player in data.get("players", [])]
        game.phase = DiceGamePhase(data.get("phase", DiceGamePhase.WAITING.value))
        game.last_rolls = data.get("last_rolls", {})
        game.winner_person_ids = data.get("winner_person_ids", [])
        game.game_id = data.get("game_id")
        if game.game_id is None and game.phase != DiceGamePhase.WAITING:
            game.game_id = str(uuid.uuid4())
        return game
