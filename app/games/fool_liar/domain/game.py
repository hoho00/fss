import random
import re
import uuid
import math
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum

from app.games.fool_liar.domain.word_repository import Word, WordPair


class FoolLiarPhase(str, Enum):
    WAITING = "WAITING"
    EXPLAINING = "EXPLAINING"
    VOTING = "VOTING"
    REVOTING = "REVOTING"
    ANSWERING = "ANSWERING"
    FINISHED = "FINISHED"


@dataclass
class FoolLiarPlayer:
    person_id: str
    display_name: str


class FoolLiarGame:
    MIN_PLAYERS = 3
    MAX_PLAYERS = 10
    PHASE_SECONDS = 60
    DESCRIPTION_ROUNDS = 2

    def __init__(self):
        self.players: list[FoolLiarPlayer] = []
        self.phase = FoolLiarPhase.WAITING
        self.description_order: list[str] = []
        self.current_description_round = 1
        self.current_description_index = 0
        self.word_pair: WordPair | None = None
        self.general_word: Word | None = None
        self.fool_word: Word | None = None
        self.personal_words: dict[str, str] = {}
        self.fool_person_id: str | None = None
        self.descriptions: list[dict] = []
        self.votes: dict[str, str] = {}
        self.first_vote_result: dict[str, int] = {}
        self.revote_candidates: list[str] = []
        self.revote_count = 0
        self.final_accused_person_id: str | None = None
        self.answer_text: str | None = None
        self.answer_correct: bool | None = None
        self.winner_person_ids: list[str] = []
        self.deadline_at: str | None = None
        self.game_id: str | None = None
        self.normal_finished = False
        self.stats_recorded = False
        self.finish_reason: str | None = None

    @property
    def game_over(self) -> bool:
        return self.phase == FoolLiarPhase.FINISHED

    def can_change_game(self) -> bool:
        return self.phase in {FoolLiarPhase.WAITING, FoolLiarPhase.FINISHED}

    def join(self, person_id: str, display_name: str) -> str:
        if self.phase != FoolLiarPhase.WAITING:
            raise ValueError("모집 중에만 참가할 수 있습니다.")
        if any(player.person_id == person_id for player in self.players):
            raise ValueError("이미 참가했습니다.")
        if len(self.players) >= self.MAX_PLAYERS:
            raise ValueError("바보 라이어게임은 최대 10명까지 참가할 수 있습니다.")
        self.players.append(FoolLiarPlayer(person_id, display_name))
        return f"{display_name}님이 바보 라이어게임에 참가했습니다. ({len(self.players)}/{self.MAX_PLAYERS}명)"

    def cancel_join(self, person_id: str) -> str:
        if self.phase != FoolLiarPhase.WAITING:
            raise ValueError("모집 중에만 참가를 취소할 수 있습니다.")
        player = self._player(person_id)
        self.players = [item for item in self.players if item.person_id != person_id]
        return f"{player.display_name}님이 참가를 취소했습니다. ({len(self.players)}명)"

    def start(
        self,
        word_pair: WordPair,
        now: datetime | None = None,
        rng: random.Random | None = None,
    ) -> str:
        if self.phase != FoolLiarPhase.WAITING:
            raise ValueError("이미 게임이 진행 중입니다.")
        if len(self.players) < self.MIN_PLAYERS:
            raise ValueError("바보 라이어게임은 최소 3명이 참가해야 시작할 수 있습니다.")

        rng = rng or random
        self.game_id = str(uuid.uuid4())
        self.word_pair = word_pair
        words = [word_pair.a, word_pair.b]
        rng.shuffle(words)
        self.general_word, self.fool_word = words
        self.fool_person_id = rng.choice(self.players).person_id
        self.description_order = [player.person_id for player in self.players]
        rng.shuffle(self.description_order)
        self.personal_words = {
            player.person_id: (
                self.fool_word.text if player.person_id == self.fool_person_id else self.general_word.text
            )
            for player in self.players
        }
        self.phase = FoolLiarPhase.EXPLAINING
        self.current_description_round = 1
        self.current_description_index = 0
        self.descriptions = []
        self.votes = {}
        self.first_vote_result = {}
        self.revote_candidates = []
        self.revote_count = 0
        self.final_accused_person_id = None
        self.answer_text = None
        self.answer_correct = None
        self.winner_person_ids = []
        self.normal_finished = False
        self.stats_recorded = False
        self.finish_reason = None
        self._set_deadline(now)
        return self._start_message()

    def rollback_start(self) -> None:
        self.phase = FoolLiarPhase.WAITING
        self.description_order = []
        self.current_description_round = 1
        self.current_description_index = 0
        self.word_pair = None
        self.general_word = None
        self.fool_word = None
        self.personal_words = {}
        self.fool_person_id = None
        self.descriptions = []
        self.votes = {}
        self.deadline_at = None
        self.game_id = None

    def personal_word(self, person_id: str) -> str:
        if person_id not in self.personal_words:
            raise ValueError("진행 중인 게임 참가자만 제시어를 확인할 수 있습니다.")
        return f"당신의 제시어: {self.personal_words[person_id]}\n역할은 공개되지 않습니다."

    def submit_description(self, person_id: str, text: str, now: datetime | None = None) -> str:
        if self.phase != FoolLiarPhase.EXPLAINING:
            raise ValueError("현재는 설명 단계가 아닙니다.")
        self._ensure_deadline_open(now)
        current_id = self.current_actor_person_id()
        if person_id != current_id:
            raise ValueError(f"현재 설명 차례는 {self._player_name(current_id)}님입니다.")
        text = text.strip()
        if not text:
            raise ValueError("설명 내용을 입력해주세요. 예: @FSS 설명 따뜻할 때 좋아요")

        self.descriptions.append(
            {
                "round": self.current_description_round,
                "person_id": person_id,
                "display_name": self._player_name(person_id),
                "text": text,
                "skipped": False,
            }
        )
        message = f"{self._player_name(person_id)}님의 설명: {text}"
        self._advance_description(now)
        return f"{message}\n\n{self.status(now)}"

    def submit_vote(self, voter_id: str, target: str, now: datetime | None = None) -> str:
        if self.phase not in {FoolLiarPhase.VOTING, FoolLiarPhase.REVOTING}:
            raise ValueError("현재는 투표 단계가 아닙니다.")
        self._ensure_deadline_open(now)
        self._player(voter_id)
        target_id = self.resolve_player(target)
        if target_id == voter_id:
            raise ValueError("자기 자신에게는 투표할 수 없습니다.")
        if self.phase == FoolLiarPhase.REVOTING and target_id not in self.revote_candidates:
            names = ", ".join(self._player_name(item) for item in self.revote_candidates)
            raise ValueError(f"재투표 대상에게만 투표할 수 있습니다: {names}")

        self.votes[voter_id] = target_id
        if len(self.votes) == len(self.players):
            return self._finalize_vote(now)
        return f"{self._player_name(voter_id)}님의 투표가 접수되었습니다. ({len(self.votes)}/{len(self.players)})"

    def submit_answer(self, person_id: str, answer: str, now: datetime | None = None) -> str:
        if self.phase != FoolLiarPhase.ANSWERING:
            raise ValueError("현재는 정답 제출 단계가 아닙니다.")
        self._ensure_deadline_open(now)
        if person_id != self.fool_person_id:
            raise ValueError("최종 지목된 참가자만 정답을 제출할 수 있습니다.")
        answer = answer.strip()
        if not answer:
            raise ValueError("정답을 입력해주세요.")
        self.answer_text = answer
        accepted = {self._normalize_answer(self.general_word.text)}
        accepted.update(self._normalize_answer(alias) for alias in self.general_word.aliases)
        self.answer_correct = self._normalize_answer(answer) in accepted
        if self.answer_correct:
            self._finish([self.fool_person_id], "바보가 일반 제시어를 맞혔습니다.")
        else:
            self._finish(self._normal_player_ids(), "바보가 일반 제시어를 맞히지 못했습니다.")
        return self.final_result_text()

    def handle_timeout(self, now: datetime | None = None) -> str:
        if self.phase == FoolLiarPhase.EXPLAINING:
            person_id = self.current_actor_person_id()
            self.descriptions.append(
                {
                    "round": self.current_description_round,
                    "person_id": person_id,
                    "display_name": self._player_name(person_id),
                    "text": "(시간 초과로 설명 생략)",
                    "skipped": True,
                }
            )
            message = f"{self._player_name(person_id)}님은 시간 초과로 설명을 생략했습니다."
            self._advance_description(now)
            return f"{message}\n\n{self.status(now)}"
        if self.phase in {FoolLiarPhase.VOTING, FoolLiarPhase.REVOTING}:
            return self._finalize_vote(now)
        if self.phase == FoolLiarPhase.ANSWERING:
            self.answer_correct = False
            self._finish(self._normal_player_ids(), "바보가 제한시간 안에 정답을 제출하지 못했습니다.")
            return self.final_result_text()
        return self.status(now)

    def reset(self) -> str:
        self.__init__()
        return "바보 라이어게임을 종료하고 모집 상태로 초기화했습니다."

    def restart_with_same_players(self) -> str:
        if self.phase != FoolLiarPhase.FINISHED:
            raise ValueError("게임이 끝난 뒤 새게임을 준비할 수 있습니다.")
        players = self.players[:]
        self.__init__()
        self.players = players
        return "같은 참가자로 새 바보 라이어게임을 준비했습니다. 시작을 눌러주세요."

    def current_actor_person_id(self) -> str | None:
        if self.phase == FoolLiarPhase.EXPLAINING and self.current_description_index < len(self.description_order):
            return self.description_order[self.current_description_index]
        if self.phase == FoolLiarPhase.ANSWERING:
            return self.fool_person_id
        return None

    def remaining_seconds(self, now: datetime | None = None) -> int:
        if not self.deadline_at:
            return 0
        deadline = datetime.fromisoformat(self.deadline_at)
        return max(0, math.ceil((deadline - (now or datetime.now(timezone.utc))).total_seconds()))

    def status(self, now: datetime | None = None) -> str:
        if self.phase == FoolLiarPhase.WAITING:
            names = ", ".join(player.display_name for player in self.players) or "없음"
            return f"바보 라이어게임 모집 중 ({len(self.players)}/{self.MAX_PLAYERS}명): {names}"
        if self.phase == FoolLiarPhase.EXPLAINING:
            current = self.current_actor_person_id()
            if self.current_description_index + 1 < len(self.description_order):
                next_id = self.description_order[self.current_description_index + 1]
            elif self.current_description_round < self.DESCRIPTION_ROUNDS:
                next_id = self.description_order[0]
            else:
                next_id = None
            next_name = self._player_name(next_id) if next_id else "없음"
            return (
                f"설명 단계 ({self.current_description_round}/{self.DESCRIPTION_ROUNDS}바퀴, "
                f"{self.current_description_index + 1}/{len(self.description_order)}명)\n"
                f"현재 설명자: {self._player_name(current)} / 다음 설명자: {next_name} / 남은 시간: {self.remaining_seconds(now)}초"
            )
        if self.phase in {FoolLiarPhase.VOTING, FoolLiarPhase.REVOTING}:
            label = "재투표" if self.phase == FoolLiarPhase.REVOTING else "투표"
            return f"{label} 단계: {len(self.votes)}/{len(self.players)}명 투표 완료 / 남은 시간: {self.remaining_seconds(now)}초"
        if self.phase == FoolLiarPhase.ANSWERING:
            return (
                f"최종 지목된 {self._player_name(self.final_accused_person_id)}님에게 "
                f"제시어 정답 기회가 주어졌습니다. 남은 시간: {self.remaining_seconds(now)}초"
            )
        return self.final_result_text()

    def final_result_text(self) -> str:
        if not self.game_over or not self.word_pair:
            return self.status()
        explanations = "\n".join(
            f"- {item.get('round', 1)}바퀴 {item['display_name']}: {item['text']}" for item in self.descriptions
        ) or "- 없음"
        vote_lines = "\n".join(
            f"- {self._player_name(voter)} → {self._player_name(target)}" for voter, target in self.votes.items()
        ) or "- 투표 없음"
        first_counts = " / ".join(
            f"{self._player_name(target)} {count}표"
            for target, count in self.first_vote_result.items()
        ) or "투표 없음"
        accused = self._player_name(self.final_accused_person_id) if self.final_accused_person_id else "없음"
        winners = ", ".join(self._player_name(item) for item in self.winner_person_ids)
        return (
            f"바보 라이어게임 종료\n\n카테고리: {self.word_pair.category}\n"
            f"일반 제시어: {self.general_word.text}\n바보 제시어: {self.fool_word.text}\n"
            f"바보 플레이어: {self._player_name(self.fool_person_id)}\n\n"
            f"전체 설명\n{explanations}\n\n1차 득표: {first_counts}\n"
            f"최종 투표\n{vote_lines}\n최종 지목: {accused}\n\n"
            f"결과: {self.finish_reason}\n최종 승자: {winners}"
        )

    def resolve_player(self, value: str) -> str:
        value = value.strip()
        for player in self.players:
            if player.person_id == value or player.display_name.casefold() == value.casefold():
                return player.person_id
        raise ValueError("투표할 참가자를 찾을 수 없습니다.")

    def _advance_description(self, now: datetime | None) -> None:
        self.current_description_index += 1
        if self.current_description_index >= len(self.description_order):
            if self.current_description_round < self.DESCRIPTION_ROUNDS:
                self.current_description_round += 1
                self.current_description_index = 0
            else:
                self.phase = FoolLiarPhase.VOTING
                self.votes = {}
        self._set_deadline(now)

    def _finalize_vote(self, now: datetime | None) -> str:
        counts: dict[str, int] = {}
        for target in self.votes.values():
            counts[target] = counts.get(target, 0) + 1
        if self.phase == FoolLiarPhase.VOTING:
            self.first_vote_result = counts.copy()
        if not counts:
            self._finish([self.fool_person_id], "아무도 투표하지 않아 바보가 승리했습니다.")
            return self.final_result_text()
        highest = max(counts.values())
        leaders = [person_id for person_id, count in counts.items() if count == highest]
        if len(leaders) > 1:
            if self.phase == FoolLiarPhase.REVOTING:
                self._finish([self.fool_person_id], "재투표도 동률이어서 바보가 승리했습니다.")
                return self.final_result_text()
            self.phase = FoolLiarPhase.REVOTING
            self.revote_candidates = leaders
            self.revote_count = 1
            self.votes = {}
            self._set_deadline(now)
            names = ", ".join(self._player_name(item) for item in leaders)
            return f"최다 득표가 동률입니다. 다음 대상만 재투표해주세요: {names}\n{self.status(now)}"

        accused = leaders[0]
        self.final_accused_person_id = accused
        if accused != self.fool_person_id:
            self._finish([self.fool_person_id], f"{self._player_name(accused)}님을 잘못 지목해 바보가 승리했습니다.")
            return self.final_result_text()
        self.phase = FoolLiarPhase.ANSWERING
        self.votes = counts and self.votes or {}
        self._set_deadline(now)
        return f"최종 지목이 확정되었습니다. 지목된 참가자의 제시어 정답 기회를 진행합니다.\n{self.status(now)}"

    def _finish(self, winners: list[str], reason: str) -> None:
        self.phase = FoolLiarPhase.FINISHED
        self.winner_person_ids = list(dict.fromkeys(winners))
        self.finish_reason = reason
        self.normal_finished = True
        self.deadline_at = None

    def _normal_player_ids(self) -> list[str]:
        return [player.person_id for player in self.players if player.person_id != self.fool_person_id]

    def _start_message(self) -> str:
        order = " → ".join(self._player_name(item) for item in self.description_order)
        return (
            f"바보 라이어게임을 시작합니다. 설명은 총 {self.DESCRIPTION_ROUNDS}바퀴 진행합니다.\n"
            f"설명 순서: {order}\n{self.status()}"
        )

    def _set_deadline(self, now: datetime | None) -> None:
        current = now or datetime.now(timezone.utc)
        self.deadline_at = (current + timedelta(seconds=self.PHASE_SECONDS)).isoformat()

    def _ensure_deadline_open(self, now: datetime | None = None) -> None:
        if self.deadline_at and self.remaining_seconds(now) <= 0:
            raise ValueError("제한시간이 종료되었습니다. 시간 초과 처리를 기다려주세요.")

    def _player(self, person_id: str) -> FoolLiarPlayer:
        for player in self.players:
            if player.person_id == person_id:
                return player
        raise ValueError("게임 참가자를 찾을 수 없습니다.")

    def _player_name(self, person_id: str | None) -> str:
        if person_id is None:
            return "없음"
        return self._player(person_id).display_name

    @staticmethod
    def _normalize_answer(value: str) -> str:
        return re.sub(r"\s+", "", value.strip()).casefold()

    def to_dict(self) -> dict:
        return {
            "players": [asdict(player) for player in self.players],
            "phase": self.phase.value,
            "description_order": self.description_order,
            "current_description_round": self.current_description_round,
            "current_description_index": self.current_description_index,
            "word_pair": self.word_pair.to_dict() if self.word_pair else None,
            "general_word": self.general_word.to_dict() if self.general_word else None,
            "fool_word": self.fool_word.to_dict() if self.fool_word else None,
            "personal_words": self.personal_words,
            "fool_person_id": self.fool_person_id,
            "descriptions": self.descriptions,
            "votes": self.votes,
            "first_vote_result": self.first_vote_result,
            "revote_candidates": self.revote_candidates,
            "revote_count": self.revote_count,
            "final_accused_person_id": self.final_accused_person_id,
            "answer_text": self.answer_text,
            "answer_correct": self.answer_correct,
            "winner_person_ids": self.winner_person_ids,
            "deadline_at": self.deadline_at,
            "game_id": self.game_id,
            "normal_finished": self.normal_finished,
            "stats_recorded": self.stats_recorded,
            "finish_reason": self.finish_reason,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FoolLiarGame":
        game = cls()
        game.players = [FoolLiarPlayer(**item) for item in data.get("players", [])]
        game.phase = FoolLiarPhase(data.get("phase", FoolLiarPhase.WAITING.value))
        game.description_order = data.get("description_order", [])
        game.current_description_round = data.get("current_description_round", 1)
        game.current_description_index = data.get("current_description_index", 0)
        game.word_pair = WordPair.from_dict(data["word_pair"]) if data.get("word_pair") else None
        game.general_word = Word.from_dict(data["general_word"]) if data.get("general_word") else None
        game.fool_word = Word.from_dict(data["fool_word"]) if data.get("fool_word") else None
        for field in ["personal_words", "descriptions", "votes", "first_vote_result", "revote_candidates", "winner_person_ids"]:
            setattr(game, field, data.get(field, getattr(game, field)))
        for field in ["fool_person_id", "final_accused_person_id", "answer_text", "answer_correct", "deadline_at", "game_id", "finish_reason"]:
            setattr(game, field, data.get(field))
        game.revote_count = data.get("revote_count", 0)
        game.normal_finished = bool(data.get("normal_finished", False))
        game.stats_recorded = bool(data.get("stats_recorded", False))
        return game
