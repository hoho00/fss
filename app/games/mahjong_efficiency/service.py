from __future__ import annotations

import random
import threading
from dataclasses import dataclass, field
from uuid import uuid4

from app.commands.parser import CommandParser
from app.games.mahjong_efficiency.card_builder import build_hand_card, build_result_card
from app.games.mahjong_efficiency.engine import (
    counts_from_tiles, evaluate_discards, shanten, tile_label,
)
from app.games.mahjong_efficiency.store import MahjongEfficiencyStore


COMMANDS = {
    "패효율 시작", "마작 시작", "패효율 상태", "패효율 기록",
    "패효율 종료", "패효율 도움말",
}


@dataclass
class TileInstance:
    instance_id: str
    tile: int

    def to_dict(self):
        return {"instance_id": self.instance_id, "tile": self.tile}

    @classmethod
    def from_dict(cls, data):
        return cls(str(data["instance_id"]), int(data["tile"]))


@dataclass
class MahjongSession:
    game_id: str
    person_id: str
    room_id: str
    round_id: int
    state_version: int
    hand: list[TileInstance]
    wall: list[TileInstance]
    drawn_tile_instance_id: str | None = None
    discards: list[dict] = field(default_factory=list)
    history: list[dict] = field(default_factory=list)
    turns: int = 0
    correct: int = 0
    loss: int = 0
    worsened: int = 0
    acquired_efficiency: int = 0
    possible_efficiency: int = 0

    @property
    def drawn_tile(self) -> TileInstance | None:
        return next(
            (item for item in self.hand if item.instance_id == self.drawn_tile_instance_id),
            None,
        )

    @property
    def base_hand(self) -> list[TileInstance]:
        return [item for item in self.hand if item.instance_id != self.drawn_tile_instance_id]

    def to_dict(self):
        return {
            "game_id": self.game_id, "person_id": self.person_id, "room_id": self.room_id,
            "round_id": self.round_id, "state_version": self.state_version,
            "hand": [item.to_dict() for item in self.hand],
            "wall": [item.to_dict() for item in self.wall],
            "drawn_tile_instance_id": self.drawn_tile_instance_id,
            "discards": self.discards, "history": self.history,
            "turns": self.turns, "correct": self.correct, "loss": self.loss,
            "worsened": self.worsened,
            "acquired_efficiency": self.acquired_efficiency,
            "possible_efficiency": self.possible_efficiency,
        }

    @classmethod
    def from_dict(cls, data):
        hand = [TileInstance.from_dict(item) for item in data["hand"]]
        drawn_id = data.get("drawn_tile_instance_id")
        if not drawn_id or len(hand) != 14 or not any(
            item.instance_id == drawn_id for item in hand
        ):
            raise ValueError("legacy mahjong session has no recoverable drawn tile")
        discards = []
        for index, item in enumerate(data.get("discards", [])):
            if isinstance(item, dict):
                discards.append({"instance_id": str(item["instance_id"]), "tile": int(item["tile"])})
            else:
                discards.append({"instance_id": f"legacy-{index}", "tile": int(item)})
        return cls(
            game_id=str(data["game_id"]), person_id=str(data["person_id"]),
            room_id=str(data.get("room_id", "")), round_id=int(data["round_id"]),
            state_version=int(data["state_version"]),
            hand=hand,
            wall=[TileInstance.from_dict(item) for item in data["wall"]],
            drawn_tile_instance_id=str(drawn_id), discards=discards,
            history=list(data.get("history", [])),
            turns=int(data.get("turns", 0)), correct=int(data.get("correct", 0)),
            loss=int(data.get("loss", 0)), worsened=int(data.get("worsened", 0)),
            acquired_efficiency=int(data.get("acquired_efficiency", 0)),
            possible_efficiency=int(data.get("possible_efficiency", 0)),
        )


def empty_record() -> dict:
    return {
        "completed_games": 0, "total_discards": 0, "correct_discards": 0,
        "total_efficiency_loss": 0, "current_streak": 0, "best_streak": 0,
        "shanten_worsened_discards": 0,
        "total_acquired_efficiency": 0, "total_possible_efficiency": 0,
    }


class MahjongEfficiencyService:
    def __init__(self, store=None, rng=None, command_parser=None):
        self.store = store or MahjongEfficiencyStore()
        self.rng = rng or random.SystemRandom()
        self.command_parser = command_parser or CommandParser()
        data = self.store.load()
        self.sessions = {}
        self.invalidated_sessions: set[str] = set()
        for person_id, value in data.get("sessions", {}).items():
            try:
                self.sessions[person_id] = MahjongSession.from_dict(value)
            except (KeyError, TypeError, ValueError):
                self.invalidated_sessions.add(person_id)
        self.records = data.get("records", {})
        self._locks: dict[str, threading.RLock] = {}
        self._locks_guard = threading.Lock()

    def normalized_command(self, text: str) -> str:
        return " ".join(self.command_parser.normalize(text).split())

    def is_command(self, text: str) -> bool:
        return self.normalized_command(text) in COMMANDS

    def handle_command(self, client, message: dict) -> dict:
        command = self.normalized_command(message.get("text", ""))
        person_id = message.get("personId")
        room_id = message.get("roomId")
        room_type = message.get("roomType")
        if not person_id or not room_id:
            return {"ok": False, "message": "사용자 또는 Webex 방 정보를 찾을 수 없습니다."}
        if room_type != "direct":
            try:
                client.send_direct_message(
                    person_id=person_id,
                    markdown="마작 패효율은 봇과의 개인채팅에서 이용해주세요.",
                )
            except Exception:
                client.send_room_message(
                    room_id=room_id,
                    markdown="개인채팅 안내를 보내지 못했습니다. 잠시 후 다시 시도해주세요.",
                )
                return {"ok": True, "ignored": True, "reason": "direct message failed"}
            return {"ok": True, "ignored": True, "reason": "direct room required"}
        with self._person_lock(person_id):
            if person_id in self.invalidated_sessions:
                self.invalidated_sessions.remove(person_id)
                client.send_room_message(
                    room_id=room_id,
                    markdown="저장 형식이 변경되어 진행 중이던 패효율 게임을 다시 시작해주세요.",
                )
                self._save()
                if command not in {"패효율 시작", "마작 시작"}:
                    return {"ok": True, "mahjong_efficiency": True, "invalidated": True}
            if command in {"패효율 시작", "마작 시작"}:
                existing = self.sessions.get(person_id)
                if existing:
                    client.send_room_message(
                        room_id=room_id,
                        markdown="이미 진행 중인 패효율 게임을 이어서 표시합니다.",
                    )
                    self._send_hand(client, existing)
                    return {"ok": True, "mahjong_efficiency": True, "resumed": True}
                session = self._new_session(person_id, room_id)
                self.sessions[person_id] = session
                self._save()
                self._send_hand(client, session)
            elif command == "패효율 상태":
                session = self.sessions.get(person_id)
                message_text = self._status(session) if session else "진행 중인 패효율 게임이 없습니다."
                client.send_room_message(room_id=room_id, markdown=message_text)
            elif command == "패효율 기록":
                client.send_room_message(room_id=room_id, markdown=self._record_text(person_id))
            elif command == "패효율 종료":
                existed = self.sessions.pop(person_id, None)
                self._save()
                client.send_room_message(room_id=room_id, markdown="패효율 게임을 종료했습니다." if existed else "진행 중인 패효율 게임이 없습니다.")
            else:
                client.send_room_message(room_id=room_id, markdown=(
                    "패효율 명령: 패효율 시작 / 패효율 상태 / 패효율 기록 / "
                    "패효율 종료 / 패효율 도움말"
                ))
        return {"ok": True, "mahjong_efficiency": True}

    def handle_action(self, client, action: dict) -> dict:
        inputs = action.get("inputs") or {}
        person_id = action.get("personId")
        room_id = action.get("roomId")
        if not person_id or not room_id:
            return {"ok": False, "message": "action 사용자 정보를 찾을 수 없습니다."}
        with self._person_lock(person_id):
            session = self.sessions.get(person_id)
            if session is None or session.room_id != room_id:
                return self._action_notice(client, room_id, "본인의 진행 중인 패효율 게임이 아닙니다.", "not owner")
            if (
                inputs.get("game_id") != session.game_id
                or _safe_int(inputs.get("round_id")) != session.round_id
                or _safe_int(inputs.get("state_version")) != session.state_version
            ):
                return self._action_notice(client, room_id, "이미 처리된 선택입니다.", "stale action")
            instance_id = inputs.get("tile_instance_id")
            selected_instance = next((item for item in session.hand if item.instance_id == instance_id), None)
            if selected_instance is None:
                return self._action_notice(client, room_id, "선택한 패를 현재 손패에서 찾을 수 없습니다.", "invalid tile")

            wall_counts = counts_from_tiles(item.tile for item in session.wall)
            evaluation = evaluate_discards(
                [item.tile for item in session.hand], remaining_counts=wall_counts
            )
            selected = evaluation.for_tile(selected_instance.tile)
            round_id = session.round_id
            drawn_tile = session.drawn_tile
            if drawn_tile is None:
                self.sessions.pop(person_id, None)
                self._save()
                return self._action_notice(
                    client, room_id,
                    "저장 형식이 변경되어 진행 중이던 패효율 게임을 다시 시작해주세요.",
                    "invalid drawn tile",
                )
            is_tsumogiri = selected_instance.instance_id == drawn_tile.instance_id
            acquired = selected.ukeire_count if selected.shanten == evaluation.best_shanten else 0
            possible = evaluation.highest_ukeire_count
            turn_loss = max(0, possible - acquired)
            result = {
                "selected": selected,
                "best_discards": evaluation.best_discards,
                "highest_ukeire_count": evaluation.highest_ukeire_count,
                "round_id": round_id,
                "drawn_tile": drawn_tile,
                "discarded_tile": selected_instance,
                "is_tsumogiri": is_tsumogiri,
                "acquired_efficiency": acquired,
                "efficiency_loss": turn_loss,
            }
            session.hand.remove(selected_instance)
            session.discards.append({
                "instance_id": selected_instance.instance_id,
                "tile": selected_instance.tile,
            })
            session.turns += 1
            session.correct += int(selected.is_best)
            session.loss += turn_loss
            session.worsened += int(selected.shanten_loss > 0)
            session.acquired_efficiency += acquired
            session.possible_efficiency += possible
            history_item = {
                "round_id": round_id,
                "drawn_tile_instance_id": drawn_tile.instance_id,
                "drawn_tile_type": drawn_tile.tile,
                "discarded_tile_instance_id": selected_instance.instance_id,
                "discarded_tile_type": selected_instance.tile,
                "is_tsumogiri": is_tsumogiri,
                "selected_shanten": selected.shanten,
                "best_shanten": evaluation.best_shanten,
                "selected_ukeire_count": selected.ukeire_count,
                "highest_ukeire_count": possible,
                "acquired_efficiency": acquired,
                "efficiency_loss": turn_loss,
                "best_discards": list(evaluation.best_discards),
                "effective_tiles": [
                    {"tile": tile, "count": count} for tile, count in selected.ukeire
                ],
            }
            session.history.append(history_item)
            self._update_record(person_id, selected, acquired, possible, turn_loss)
            client.send_room_card(room_id=room_id, markdown="패효율 타패 결과", card=build_result_card(result))

            if shanten([item.tile for item in session.hand]) == 0:
                self.records[person_id]["completed_games"] += 1
                self.sessions.pop(person_id, None)
                self._save()
                client.send_room_message(
                    room_id=room_id,
                    markdown=(
                        "텐파이에 도달해 게임을 완료했습니다.\n\n"
                        + self._history_text(session) + "\n\n" + self._record_text(person_id)
                    ),
                )
                return {"ok": True, "completed": True, "result": result}

            if not session.wall:
                self.sessions.pop(person_id, None)
                self._save()
                return self._action_notice(client, room_id, "패산이 모두 소진되어 게임을 종료했습니다.", "wall empty")
            drawn = session.wall.pop(self.rng.randrange(len(session.wall)))
            session.hand.append(drawn)
            session.drawn_tile_instance_id = drawn.instance_id
            session.round_id += 1
            session.state_version += 1
            self._save()
            self._send_hand(client, session)
            return {"ok": True, "completed": False, "result": result}

    def _new_session(self, person_id: str, room_id: str) -> MahjongSession:
        wall = [TileInstance(str(uuid4()), tile) for tile in range(34) for _ in range(4)]
        self.rng.shuffle(wall)
        hand = [wall.pop() for _ in range(13)]
        drawn = wall.pop()
        hand.append(drawn)
        return MahjongSession(
            str(uuid4()), person_id, room_id, 1, 1, hand, wall,
            drawn_tile_instance_id=drawn.instance_id,
        )

    def _update_record(self, person_id, selected, acquired, possible, turn_loss) -> None:
        record = self.records.setdefault(person_id, empty_record())
        for key, value in empty_record().items():
            record.setdefault(key, value)
        record["total_discards"] += 1
        record["correct_discards"] += int(selected.is_best)
        record["total_efficiency_loss"] += turn_loss
        record["total_acquired_efficiency"] += acquired
        record["total_possible_efficiency"] += possible
        record["shanten_worsened_discards"] += int(selected.shanten_loss > 0)
        record["current_streak"] = record["current_streak"] + 1 if selected.is_best else 0
        record["best_streak"] = max(record["best_streak"], record["current_streak"])

    def _record_text(self, person_id: str) -> str:
        record = {**empty_record(), **self.records.get(person_id, {})}
        total = record["total_discards"]
        accuracy = record["correct_discards"] / total * 100 if total else 0
        possible = record["total_possible_efficiency"]
        efficiency_rate = record["total_acquired_efficiency"] / possible * 100 if possible else 0
        average_loss = record["total_efficiency_loss"] / total if total else 0
        return (
            f"패효율 개인 기록\n완료 게임: {record['completed_games']}\n"
            f"누적 획득 효율: {record['total_acquired_efficiency']}장\n"
            f"획득 가능 최고 효율: {possible}장\n"
            f"효율 획득률: {efficiency_rate:.1f}%\n"
            f"누적 손실: {record['total_efficiency_loss']}장 · 평균 손실: {average_loss:.2f}장\n"
            f"최선 타패: {record['correct_discards']}/{total}회 (참고 {accuracy:.1f}%)\n"
            f"현재/최고 연속 정답: {record['current_streak']}/{record['best_streak']}\n"
            f"샨텐 악화 타패: {record['shanten_worsened_discards']}회"
        )

    @staticmethod
    def _status(session) -> str:
        base = " · ".join(tile_label(item.tile) for item in sorted(session.base_hand, key=lambda item: item.tile))
        drawn = tile_label(session.drawn_tile.tile) if session.drawn_tile else "없음"
        discards = " · ".join(tile_label(item["tile"]) for item in session.discards) or "없음"
        current_shanten = shanten([item.tile for item in session.hand])
        return (
            f"패효율 진행 중 · {session.round_id}순\n"
            f"기본 손패: {base}\n이번 쯔모: {drawn}\n내 버림패: {discards}\n"
            f"현재 샨텐: {current_shanten}\n"
            f"누적 획득/가능 효율: {session.acquired_efficiency}/{session.possible_efficiency}장\n"
            + MahjongEfficiencyService._history_text(session)
        )

    @staticmethod
    def _history_text(session) -> str:
        if not session.history:
            return "최근 이력: 없음"
        lines = []
        for item in session.history[-5:]:
            suffix = "(쯔모기리)" if item["is_tsumogiri"] else ""
            lines.append(
                f"{item['round_id']}순: 쯔모 {tile_label(item['drawn_tile_type'])} → "
                f"타패 {tile_label(item['discarded_tile_type'])}{suffix} · "
                f"손실 {item['efficiency_loss']}장"
            )
        return "최근 이력\n" + "\n".join(lines)

    @staticmethod
    def _action_notice(client, room_id, message, reason):
        client.send_room_message(room_id=room_id, markdown=message)
        return {"ok": True, "ignored": True, "reason": reason}

    def _send_hand(self, client, session):
        client.send_room_card(room_id=session.room_id, markdown="버릴 마작패를 선택하세요.", card=build_hand_card(session))

    def _save(self):
        self.store.save({
            "sessions": {key: value.to_dict() for key, value in self.sessions.items()},
            "records": self.records,
        })

    def _person_lock(self, person_id):
        with self._locks_guard:
            return self._locks.setdefault(person_id, threading.RLock())


def _safe_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
