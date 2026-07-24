from __future__ import annotations

import os
import random
import threading
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.commands.parser import CommandParser
from app.games.mahjong_efficiency.battle_card_builder import (
    build_battle_final_card, build_battle_menu_card, build_battle_result_card,
    build_battle_round_card, build_battle_status_card, build_game_status_selector_card,
)
from app.games.mahjong_efficiency.engine import counts_from_tiles, evaluate_discards, shanten, tile_label
from app.games.mahjong_efficiency.service import TileInstance
from app.games.mahjong_efficiency.store import MahjongEfficiencyStore
from app.services.display_name import normalize_display_name


BATTLE_COMMANDS = {
    "패효율 대결", "패효율 대결 생성", "패효율 대결 참가", "패효율 대결 참가 취소",
    "패효율 대결 시작",
    "패효율 대결 상태", "패효율 대결 종료", "패효율 대결 도움말",
    "패효율 대결 방장 강퇴",
    "패효율 대결 다시 하기", "패효율 대결 메인 메뉴",
}
BATTLE_HELP = (
    "패효율 대결 도움말\n그룹방 전용 · 최소 2명 · 한 판만 진행 · 순당 10초\n"
    "하나의 공통 손패와 패산에서 한 장을 쯔모하고 한 장을 타패하며 텐파이까지 이어집니다.\n"
    "참가자 전원이 같은 공통 손패를 사용하고, 한 사람당 매 순 한 번 선택합니다.\n"
    "10초 뒤 한꺼번에 채점하며 최선 타패를 고른 참가자는 모두 +10점입니다. "
    "비효율 타패는 손실 장수만큼 감점, "
    "샨텐 악화는 최고 효율 손실과 추가 10점 감점, 미응답은 0점입니다.\n"
    "명령: 패효율 대결 / 참가 / 참가 취소 / 시작 / 상태 / 종료 / 도움말\n"
    "강제리셋 권한자 복구 명령: 패효율 대결 종료 · 패효율 대결 방장 강퇴 · 강제리셋\n"
    "Webex 버튼으로도 동일하게 조작할 수 있습니다."
)


@dataclass
class BattlePlayer:
    person_id: str
    display_name: str
    join_order: int
    score: int = 0
    wins: int = 0
    responses: int = 0
    best_discards: int = 0
    efficiency_loss: int = 0
    worsened: int = 0

    def to_dict(self): return self.__dict__.copy()
    @classmethod
    def from_dict(cls, data):
        player = cls(**data)
        player.display_name = normalize_display_name(player.display_name)
        return player


@dataclass
class BattleRound:
    hand: list[TileInstance]
    wall_counts: list[int]
    evaluation: object
    submissions: dict = field(default_factory=dict)
    wall: list[TileInstance] = field(default_factory=list)
    drawn_tile_instance_id: str | None = None

    @property
    def drawn_tile(self):
        return next(
            (item for item in self.hand if item.instance_id == self.drawn_tile_instance_id),
            None,
        )

    @property
    def base_hand(self):
        return [item for item in self.hand if item.instance_id != self.drawn_tile_instance_id]


@dataclass
class MahjongBattle:
    battle_id: str
    room_id: str
    host_person_id: str
    status: str
    players: list[BattlePlayer]
    round_id: int = 0
    turn_no: int = 0
    state_version: int = 1
    current_round: BattleRound | None = None
    round_started_at: str | None = None
    round_deadline_at: str | None = None
    completed_rounds: list[dict] = field(default_factory=list)
    phase: str = "WAITING"
    result_deadline_at: str | None = None

    def player(self, person_id):
        return next((item for item in self.players if item.person_id == person_id), None)

    def ranked_players(self):
        return sorted(self.players, key=lambda p: (-p.score, -p.wins, p.efficiency_loss, p.join_order))

    def to_dict(self):
        current = None
        if self.current_round:
            current = {
                "hand": [item.to_dict() for item in self.current_round.hand],
                "wall_counts": self.current_round.wall_counts,
                "wall": [item.to_dict() for item in self.current_round.wall],
                "drawn_tile_instance_id": self.current_round.drawn_tile_instance_id,
                "submissions": self.current_round.submissions,
                "best_shanten": self.current_round.evaluation.best_shanten,
                "best_discards": list(self.current_round.evaluation.best_discards),
                "highest_ukeire_count": self.current_round.evaluation.highest_ukeire_count,
            }
        return {
            "battle_id": self.battle_id, "room_id": self.room_id,
            "host_person_id": self.host_person_id, "status": self.status,
            "players": [item.to_dict() for item in self.players],
            "round_id": self.round_id, "turn_no": self.turn_no,
            "state_version": self.state_version, "current_round": current,
            "round_started_at": self.round_started_at,
            "round_deadline_at": self.round_deadline_at,
            "completed_rounds": self.completed_rounds,
            "phase": self.phase, "result_deadline_at": self.result_deadline_at,
        }

    @classmethod
    def from_dict(cls, data):
        battle = cls(
            str(data["battle_id"]), str(data["room_id"]), str(data["host_person_id"]),
            str(data["status"]), [BattlePlayer.from_dict(item) for item in data["players"]],
            int(data.get("round_id", 0)), int(data.get("turn_no", 0)),
            int(data.get("state_version", 1)),
            round_started_at=data.get("round_started_at"),
            round_deadline_at=data.get("round_deadline_at"),
            completed_rounds=list(data.get("completed_rounds", [])),
            phase=str(data.get("phase", "ANSWERING" if data.get("status") == "active" else "WAITING")),
            result_deadline_at=data.get("result_deadline_at"),
        )
        current = data.get("current_round")
        if current:
            if (
                battle.status == "active"
                and (not current.get("wall") or not current.get("drawn_tile_instance_id"))
            ):
                raise LegacyBattleFormatError
            hand = [TileInstance.from_dict(item) for item in current["hand"]]
            evaluation = evaluate_discards(hand=[item.tile for item in hand], remaining_counts=current["wall_counts"])
            wall = [TileInstance.from_dict(item) for item in current.get("wall", [])]
            battle.current_round = BattleRound(
                hand, list(current["wall_counts"]), evaluation,
                dict(current.get("submissions", {})), wall,
                current.get("drawn_tile_instance_id"),
            )
        return battle


class LegacyBattleFormatError(ValueError):
    pass


class MahjongBattleService:
    ROUND_SECONDS = 10

    def __init__(self, store=None, rng=None, clock=None, timer_factory=None, webex_client_factory=None, command_parser=None, is_force_reset_admin=None):
        self.store = store or MahjongEfficiencyStore(
            os.getenv("FSS_MAHJONG_BATTLE_STORE_PATH", "data/mahjong_battles.json")
        )
        self.rng = rng or random.SystemRandom()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.timer_factory = timer_factory or threading.Timer
        self.webex_client_factory = webex_client_factory
        self.command_parser = command_parser or CommandParser()
        self.is_force_reset_admin = is_force_reset_admin or (lambda _person_id: False)
        data = self.store.load()
        self.battles = {}
        self.invalidated_rooms = set()
        for key, value in data.get("battles", {}).items():
            try:
                self.battles[key] = MahjongBattle.from_dict(value)
            except LegacyBattleFormatError:
                self.invalidated_rooms.add(key)
        self.records = data.get("records", {})
        self._locks = {}
        self._locks_guard = threading.Lock()
        self._timers = {}

    def normalized_command(self, text): return " ".join(self.command_parser.normalize(text).split())
    def is_command(self, text): return self.normalized_command(text) in BATTLE_COMMANDS

    def _can_end_battle(self, battle: MahjongBattle | None, person_id: str | None) -> bool:
        if not battle or not person_id:
            return False
        if battle.host_person_id == person_id:
            return True
        if self.is_force_reset_admin(person_id):
            return True
        # Host left or was cleared: any remaining participant can end.
        return (not battle.host_person_id) and bool(battle.player(person_id))

    def clear_room(self, room_id: str) -> bool:
        """Cancel timers and drop persisted battle state for one room."""
        with self._room_lock(room_id):
            existed = room_id in self.battles or room_id in self.invalidated_rooms
            self._cancel_timer(room_id)
            self.battles.pop(room_id, None)
            self.invalidated_rooms.discard(room_id)
            if existed:
                self._save()
            return existed

    def handle_command(self, client, message):
        command = self.normalized_command(message.get("text", ""))
        room_id, person_id = message.get("roomId"), message.get("personId")
        room_type = message.get("roomType")
        action_context = message.get("actionContext")
        if not room_id or not person_id:
            return {"ok": False, "message": "사용자 또는 Webex 방 정보를 찾을 수 없습니다."}
        name = normalize_display_name(
            message.get("personDisplayName") or message.get("personEmail") or person_id
        )
        if room_type != "group":
            client.send_room_message(room_id=room_id, markdown=(
                "패효율 대결은 그룹방에서만 시작할 수 있습니다.\n"
                "개인 연습은 `패효율 시작`을 이용해주세요."
            ))
            return {"ok": True, "ignored": True, "reason": "group room required"}
        with self._room_lock(room_id):
            if room_id in self.invalidated_rooms:
                self.invalidated_rooms.remove(room_id)
                self._save()
                return self._notice(
                    client, room_id,
                    "패효율 대결 진행 방식이 변경되어 진행 중이던 대결을 다시 생성해주세요.",
                )
            battle = self.battles.get(room_id)
            mutating_commands = {
                "패효율 대결 참가", "패효율 대결 참가 취소", "패효율 대결 시작",
                "패효율 대결 종료", "패효율 대결 다시 하기", "패효율 대결 방장 강퇴",
            }
            if action_context and command in mutating_commands:
                if not self._valid_lobby_action_context(room_id, battle, action_context):
                    return {"ok": True, "ignored": True, "reason": "stale battle lobby card"}
            if command in {"패효율 대결", "패효율 대결 생성"}:
                if not battle or battle.status in {"finished", "ended"}:
                    battle = MahjongBattle(
                        str(uuid4()), room_id, person_id, "lobby",
                        [BattlePlayer(person_id, name, 0)],
                    )
                    self.battles[room_id] = battle
                    self._save()
                self._send_menu(client, battle, "패효율 대결 로비", person_id)
            elif command == "패효율 대결 다시 하기":
                if not battle or battle.status not in {"finished", "ended"}:
                    return {"ok": True, "ignored": True}
                if battle.host_person_id != person_id:
                    return self._notice(client, room_id, "방장만 다시 시작할 수 있습니다.")
                for player in battle.players:
                    player.score = player.wins = player.responses = 0
                    player.best_discards = player.efficiency_loss = player.worsened = 0
                battle.battle_id = str(uuid4()); battle.status = "lobby"; battle.phase = "WAITING"
                battle.round_id = battle.turn_no = 0; battle.state_version += 1
                battle.current_round = None; battle.completed_rounds = []
                battle.round_started_at = battle.round_deadline_at = battle.result_deadline_at = None
                self._save(); self._send_menu(client, battle, "새 대결 로비로 돌아왔습니다.", person_id)
            elif command == "패효율 대결 메인 메뉴":
                client.send_room_card(room_id=room_id, markdown="FSS 게임 선택", card=build_game_status_selector_card())
            elif command == "패효율 대결 참가":
                if not battle:
                    battle = MahjongBattle(str(uuid4()), room_id, "", "lobby", [])
                    self.battles[room_id] = battle
                if battle.status != "lobby": return self._notice(client, room_id, "참가할 대결 로비가 없습니다.")
                if battle.player(person_id): return self._notice(client, room_id, "이미 참가했습니다.")
                next_order = max((player.join_order for player in battle.players), default=-1) + 1
                battle.players.append(BattlePlayer(person_id, name, next_order))
                if not battle.host_person_id:
                    battle.host_person_id = person_id
                battle.state_version += 1
                self._save(); self._send_menu(client, battle, f"{name}님이 참가했습니다.", person_id)
            elif command == "패효율 대결 참가 취소":
                if not battle or battle.status != "lobby": return self._notice(client, room_id, "참가를 취소할 대결 로비가 없습니다.")
                if battle.host_person_id == person_id: return self._notice(client, room_id, "방장은 참가를 취소할 수 없습니다. 대결 종료를 이용해주세요.")
                player = battle.player(person_id)
                if not player: return self._notice(client, room_id, "참가 중인 대결이 아닙니다.")
                battle.players.remove(player)
                battle.state_version += 1
                self._save(); self._send_menu(client, battle, f"{player.display_name}님이 참가를 취소했습니다.", person_id)
            elif command == "패효율 대결 시작":
                if not battle or battle.status != "lobby": return self._notice(client, room_id, "시작할 대결 로비가 없습니다.")
                if battle.host_person_id != person_id: return self._notice(client, room_id, "방장만 대결을 시작할 수 있습니다.")
                if len(battle.players) < 2: return self._notice(client, room_id, "대결 시작에는 최소 2명이 필요합니다.")
                battle.status = "active"; self._start_round_locked(client, battle)
            elif command == "패효율 대결 상태":
                client.send_room_card(
                    room_id=room_id, markdown="패효율 대결 상태",
                    card=build_battle_status_card(
                        battle, self.clock(), person_id,
                        self.is_force_reset_admin(person_id),
                    ),
                )
            elif command == "패효율 대결 방장 강퇴":
                if not self.is_force_reset_admin(person_id):
                    return self._notice(client, room_id, "권한이 없습니다. 강제리셋 권한자만 방장을 강퇴할 수 있습니다.")
                if not battle or battle.status != "lobby":
                    return self._notice(client, room_id, "대기실 상태에서만 방장을 강퇴할 수 있습니다.")
                host = battle.player(battle.host_person_id)
                if not host:
                    return {"ok": True, "ignored": True, "reason": "host already left"}
                battle.players.remove(host)
                successor = min(battle.players, key=lambda player: player.join_order, default=None)
                battle.host_person_id = successor.person_id if successor else ""
                battle.state_version += 1
                self._save()
                successor_text = successor.display_name if successor else "없음"
                self._send_menu(
                    client, battle,
                    f"{host.display_name} 방장을 대기실에서 강퇴했습니다. 새 방장: {successor_text}",
                    person_id,
                )
            elif command == "패효율 대결 종료":
                if not battle or battle.status not in {"lobby", "active"}:
                    return self._notice(client, room_id, "종료할 대결이 없습니다.")
                if not self._can_end_battle(battle, person_id):
                    return self._notice(
                        client, room_id,
                        "방장 또는 강제리셋 권한자만 대결을 종료할 수 있습니다.",
                    )
                is_admin_end = (
                    battle.host_person_id != person_id
                    and self.is_force_reset_admin(person_id)
                )
                self._cancel_timer(room_id)
                battle.status = "ended"
                battle.phase = "FINISHED"
                battle.state_version += 1
                self._save()
                markdown = (
                    "관리자가 패효율 대결을 강제 종료했습니다."
                    if is_admin_end
                    else "방장이 패효율 대결을 종료했습니다."
                )
                client.send_room_card(
                    room_id=room_id, markdown=markdown,
                    card=build_battle_status_card(
                        battle, self.clock(), person_id,
                        self.is_force_reset_admin(person_id),
                    ),
                )
            else:
                client.send_room_message(room_id=room_id, markdown=BATTLE_HELP)
        return {"ok": True, "mahjong_battle": True}

    def handle_action(self, client, action):
        inputs = action.get("inputs") or {}; room_id = action.get("roomId"); person_id = action.get("personId")
        with self._room_lock(room_id):
            battle = self.battles.get(room_id)
            if not battle or battle.status != "active" or not battle.current_round:
                return {"ok": True, "ignored": True, "reason": "stale battle card"}
            if battle.phase != "ANSWERING" or inputs.get("battle_id") != battle.battle_id or _safe_int(inputs.get("turn_no")) != battle.turn_no or _safe_int(inputs.get("state_version")) != battle.state_version:
                return {"ok": True, "ignored": True, "reason": "stale battle card"}
            if self.clock() >= _parse_time(battle.round_deadline_at):
                self._finish_round_locked(client, battle, timeout=True)
                return {"ok": True, "ignored": True, "reason": "answer deadline passed"}
            player = battle.player(person_id)
            if not player: return self._notice(client, room_id, "대결 참가자만 선택할 수 있습니다.", ignored=True)
            if person_id in battle.current_round.submissions: return self._notice(client, room_id, "이번 순에서는 이미 선택했습니다.", ignored=True)
            instance = next((item for item in battle.current_round.hand if item.instance_id == inputs.get("tile_instance_id")), None)
            if not instance: return self._notice(client, room_id, "현재 라운드의 패가 아닙니다.", ignored=True)
            selected = battle.current_round.evaluation.for_tile(instance.tile)
            best_shanten = battle.current_round.evaluation.best_shanten
            worsened = selected.shanten > best_shanten
            is_best = selected.is_best
            loss = battle.current_round.evaluation.highest_ukeire_count if worsened else selected.efficiency_loss
            delta = 10 if is_best else -(loss + (10 if worsened else 0))
            submission = {
                "tile": instance.tile, "is_best": is_best, "shanten_worsened": worsened,
                "efficiency_loss": loss, "score_delta": delta,
                "tile_instance_id": instance.instance_id,
            }
            battle.current_round.submissions[person_id] = submission
            self._save()
            try: client.send_direct_message(person_id=person_id, markdown="선택이 완료되었습니다. 라운드 결과를 기다려주세요.")
            except Exception:
                client.send_room_message(room_id=room_id, markdown=f"응답 완료: {len(battle.current_round.submissions)}/{len(battle.players)}명")
            return {"ok": True, "mahjong_battle": True, "is_best": is_best}

    def restore_timers(self):
        if not self.webex_client_factory: return
        client = self.webex_client_factory()
        for battle in list(self.battles.values()):
            if battle.status != "active": continue
            deadline = battle.round_deadline_at if battle.phase == "ANSWERING" else battle.result_deadline_at
            if not deadline: continue
            if self.clock() >= _parse_time(deadline):
                with self._room_lock(battle.room_id):
                    if battle.phase == "ANSWERING": self._finish_round_locked(client, battle, timeout=True)
                    else: self._finish_result_locked(client, battle)
            else: self._schedule_timer(battle)

    def stop(self):
        for room_id in list(self._timers): self._cancel_timer(room_id)

    def _start_round_locked(self, client, battle):
        battle.round_id = 1
        battle.turn_no = 1
        battle.current_round = self._generate_round()
        battle.phase = "ANSWERING"
        self._open_turn_locked(client, battle)

    def _open_turn_locked(self, client, battle):
        client.send_room_card(room_id=battle.room_id, markdown=f"패효율 대결 · {battle.turn_no}순", card=build_battle_round_card(battle))
        now = self.clock(); battle.phase = "ANSWERING"
        battle.round_started_at = now.isoformat()
        battle.round_deadline_at = (now + timedelta(seconds=self.ROUND_SECONDS)).isoformat()
        battle.result_deadline_at = None
        self._save()
        self._schedule_timer(battle)

    def _generate_round(self):
        for _ in range(200):
            wall = [TileInstance(str(uuid4()), tile) for tile in range(34) for _ in range(4)]
            self.rng.shuffle(wall)
            base_hand = [wall.pop() for _ in range(13)]
            drawn = wall.pop()
            hand = [*base_hand, drawn]
            if shanten([item.tile for item in hand]) == -1: continue
            counts = list(counts_from_tiles(item.tile for item in wall))
            evaluation = evaluate_discards([item.tile for item in hand], remaining_counts=counts)
            if evaluation.highest_ukeire_count > 0:
                return BattleRound(
                    hand, counts, evaluation, wall=wall,
                    drawn_tile_instance_id=drawn.instance_id,
                )
        raise RuntimeError("유효한 패효율 대결 문제를 생성하지 못했습니다.")

    def _finish_round_locked(self, client, battle, timeout=False, **_ignored):
        if battle.status != "active" or battle.phase != "ANSWERING" or not battle.current_round: return
        self._cancel_timer(battle.room_id)
        round_state = battle.current_round
        correct = [s for s in round_state.submissions.values() if s["is_best"]]
        submitted_best_tiles = sorted({s["tile"] for s in correct})
        common_tile = submitted_best_tiles[0] if submitted_best_tiles else round_state.evaluation.best_discards[0]
        submitted_ids = sorted(
            s["tile_instance_id"] for s in correct if s["tile"] == common_tile
        )
        common_discard = next(
            (item for item in round_state.hand if submitted_ids and item.instance_id == submitted_ids[0]),
            None,
        ) or next(
            item for item in sorted(round_state.hand, key=lambda item: (item.tile, item.instance_id))
            if item.tile == common_tile
        )
        for person_id, submission in round_state.submissions.items():
            player = battle.player(person_id)
            if player is None:
                continue
            player.responses += 1
            player.score += submission["score_delta"]
            player.best_discards += int(submission["is_best"])
            player.efficiency_loss += submission["efficiency_loss"]
            player.worsened += int(submission["shanten_worsened"])
            if submission["is_best"]:
                player.wins += 1
        previous_drawn = round_state.drawn_tile
        result = {
            "round_id": battle.round_id, "turn_no": battle.turn_no,
            "winner_ids": [person_id for person_id, s in round_state.submissions.items() if s["is_best"]],
            "best_discards": list(round_state.evaluation.best_discards),
            "common_discard": common_discard.tile,
            "last_drawn": previous_drawn.tile if previous_drawn else None,
            "is_tsumogiri": common_discard.instance_id == round_state.drawn_tile_instance_id,
            "highest_ukeire_count": round_state.evaluation.highest_ukeire_count,
            "submissions": dict(round_state.submissions), "timeout": timeout,
        }
        result["winner_names"] = [battle.player(pid).display_name for pid in result["winner_ids"]]
        battle.completed_rounds.append(result)
        battle.state_version += 1

        next_hand = [item for item in round_state.hand if item.instance_id != common_discard.instance_id]
        current_shanten = shanten([item.tile for item in next_hand])
        result["current_shanten"] = current_shanten
        result["next_draw"] = None
        if current_shanten == 0 or not round_state.wall:
            result["final_hand"] = [item.tile for item in next_hand]
            result["waiting_tiles"] = self._waiting_tiles(next_hand, round_state.wall_counts)
            client.send_room_card(
                room_id=battle.room_id, markdown=f"{battle.turn_no}순 결과",
                card=build_battle_result_card(battle, result),
            )
            battle.status = "finished"
            battle.phase = "FINISHED"
            battle.current_round = None
            battle.round_started_at = None
            battle.round_deadline_at = None
            battle.result_deadline_at = None
            self._update_records(battle); self._save()
            client.send_room_card(
                room_id=battle.room_id, markdown="패효율 대결 최종 결과",
                card=build_battle_final_card(battle, result),
            )
            return

        drawn = round_state.wall.pop()
        round_state.wall_counts[drawn.tile] -= 1
        next_hand.append(drawn)
        result["next_draw"] = drawn.tile
        client.send_room_card(
            room_id=battle.room_id, markdown=f"{battle.turn_no}순 결과",
            card=build_battle_result_card(battle, result),
        )
        battle.current_round = BattleRound(
            next_hand,
            round_state.wall_counts,
            evaluate_discards(
                [item.tile for item in next_hand],
                remaining_counts=round_state.wall_counts,
            ),
            wall=round_state.wall,
            drawn_tile_instance_id=drawn.instance_id,
        )
        battle.phase = "RESULT"
        battle.round_deadline_at = None
        battle.result_deadline_at = (self.clock() + timedelta(seconds=self.ROUND_SECONDS)).isoformat()
        self._save(); self._schedule_timer(battle)

    def _finish_result_locked(self, client, battle):
        if battle.status != "active" or battle.phase != "RESULT": return
        self._cancel_timer(battle.room_id)
        battle.turn_no += 1; battle.state_version += 1
        self._open_turn_locked(client, battle)

    def _schedule_timer(self, battle):
        self._cancel_timer(battle.room_id)
        deadline = battle.round_deadline_at if battle.phase == "ANSWERING" else battle.result_deadline_at
        delay = max(0, (_parse_time(deadline) - self.clock()).total_seconds())
        key = (battle.battle_id, battle.turn_no, battle.state_version, battle.phase)
        timer = self.timer_factory(delay, lambda: self._timer_fired(battle.room_id, key))
        self._timers[battle.room_id] = timer
        if hasattr(timer, "daemon"): timer.daemon = True
        timer.start()

    def _timer_fired(self, room_id, key):
        if not self.webex_client_factory: return
        with self._room_lock(room_id):
            battle = self.battles.get(room_id)
            if not battle or key != (battle.battle_id, battle.turn_no, battle.state_version, battle.phase): return
            deadline = battle.round_deadline_at if battle.phase == "ANSWERING" else battle.result_deadline_at
            if self.clock() < _parse_time(deadline): self._schedule_timer(battle); return
            if battle.phase == "ANSWERING": self._finish_round_locked(self.webex_client_factory(), battle, timeout=True)
            elif battle.phase == "RESULT": self._finish_result_locked(self.webex_client_factory(), battle)

    def _cancel_timer(self, room_id):
        timer = self._timers.pop(room_id, None)
        if timer: timer.cancel()

    def _status(self, battle):
        if not battle or battle.status in {"finished", "ended"}: return "진행 중인 패효율 대결이 없습니다."
        host = battle.player(battle.host_person_id).display_name
        if battle.status == "lobby":
            names = ", ".join(item.display_name for item in battle.players)
            return f"패효율 대결 로비\n방장: {host}\n참가자: {names}\n최소 2명 · 시작 가능: {'예' if len(battle.players) >= 2 else '아니오'}"
        responses = len(battle.current_round.submissions)
        scores = " · ".join(f"{p.display_name} {p.score}점" for p in battle.ranked_players())
        remaining = max(0, int((_parse_time(battle.round_deadline_at) - self.clock()).total_seconds()))
        return f"패효율 대결 · {battle.turn_no}순\n점수: {scores}\n응답: {responses}/{len(battle.players)}명\n남은 시간: 약 {remaining}초"

    def _final_result(self, battle):
        lines = ["패효율 대결 최종 순위"]
        for rank, player in enumerate(battle.ranked_players(), 1):
            rate = player.best_discards / player.responses * 100 if player.responses else 0
            lines.append(f"{rank}. {player.display_name} · {player.score}점 · 승리 {player.wins} · 응답 {player.responses} · 최선 {player.best_discards}/{player.responses} ({rate:.1f}%) · 손실 {player.efficiency_loss}장 · 샨텐 악화 {player.worsened}")
        return "\n".join(lines)

    def _update_records(self, battle):
        for player in battle.players:
            record = self.records.setdefault(player.person_id, {"completed_battles": 0, "total_score": 0, "round_wins": 0})
            record["completed_battles"] += 1; record["total_score"] += player.score; record["round_wins"] += player.wins

    @staticmethod
    def _waiting_tiles(hand, remaining_counts):
        tiles = [item.tile for item in hand]
        return [
            tile for tile, count in enumerate(remaining_counts)
            if count > 0 and shanten([*tiles, tile]) == -1
        ]

    def _send_menu(self, client, battle, markdown, viewer_person_id=None):
        client.send_room_card(
            room_id=battle.room_id,
            markdown=markdown,
            card=build_battle_menu_card(
                battle, viewer_person_id,
                self.is_force_reset_admin(viewer_person_id),
            ),
        )
    @staticmethod
    def _valid_lobby_action_context(room_id, battle, inputs):
        if inputs.get("room_id") != room_id:
            return False
        expected_battle_id = battle.battle_id if battle else ""
        expected_version = battle.state_version if battle else 0
        return (
            inputs.get("battle_id", "") == expected_battle_id
            and _safe_int(inputs.get("state_version")) == expected_version
        )
    @staticmethod
    def _notice(client, room_id, message, ignored=False):
        client.send_room_message(room_id=room_id, markdown=message)
        return {"ok": True, "ignored": ignored, "message": message}
    def _save(self): self.store.save({"battles": {key: value.to_dict() for key, value in self.battles.items()}, "records": self.records})
    def _room_lock(self, room_id):
        with self._locks_guard: return self._locks.setdefault(room_id, threading.RLock())


def _parse_time(value): return datetime.fromisoformat(value).astimezone(timezone.utc)
def _safe_int(value):
    try: return int(value)
    except (TypeError, ValueError): return None


def _wall_from_counts(counts):
    return [
        TileInstance(f"restored-{tile}-{copy}", tile)
        for tile, count in enumerate(counts)
        for copy in range(int(count))
    ]
