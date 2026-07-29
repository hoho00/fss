from app.commands.command import CommandType
from app.commands.parser import CommandParser
from app.core.game_response import GameResponse
from app.games.fool_liar.domain.game import FoolLiarGame, FoolLiarPhase
from app.games.fool_liar.domain.word_repository import JsonWordPairRepository
from app.services.stats_store import JsonStatsStore
from app.services.display_name import clean_display_name


class FoolLiarBotService:

    def __init__(
        self,
        game: FoolLiarGame,
        command_parser: CommandParser,
        stats_store: JsonStatsStore | None = None,
        word_repository: JsonWordPairRepository | None = None,
    ):
        self.game = game
        self.command_parser = command_parser
        self.stats_store = stats_store
        self.word_repository = word_repository or JsonWordPairRepository()

    def handle_text_command(self, person_id: str, display_name: str, text: str) -> GameResponse:
        try:
            display_name = self._clean_display_name(display_name)
            self._clean_game_display_names()
            normalized = self.command_parser.normalize(text)
            private = False
            silent_public = False
            direct_messages: list[dict] = []
            abort_on_dm_failure = False
            previous_actor = self.game.current_actor_person_id()

            if normalized == "참가":
                message = self.game.join(person_id, display_name)
            elif normalized in {"참가취소", "참가 취소"}:
                message = self.game.cancel_join(person_id)
            elif normalized == "시작":
                message = self.game.start(self.word_repository.choose())
                direct_messages = [
                    {"person_id": player.person_id, "message": self.game.personal_word(player.person_id)}
                    for player in self.game.players
                ]
                current_id = self.game.current_actor_person_id()
                direct_messages.append(self._turn_word_message(current_id))
                abort_on_dm_failure = True
            elif normalized == "상태":
                message = self.game.status()
            elif normalized == "제시어":
                message = self.game.personal_word(person_id)
                private = True
                silent_public = True
            elif normalized.startswith("설명 "):
                message = self.game.submit_description(person_id, normalized[3:])
            elif normalized == "설명":
                raise ValueError("설명 내용을 입력해주세요. 예: @FSS 설명 따뜻할 때 좋아요")
            elif normalized.startswith("투표 "):
                message = self.game.submit_vote(person_id, normalized[3:])
            elif normalized == "투표":
                raise ValueError("투표 대상을 입력해주세요. 예: @FSS 투표 홍길동")
            elif normalized.startswith("정답 "):
                message = self.game.submit_answer(person_id, normalized[3:])
            elif normalized == "정답":
                raise ValueError("정답 제시어를 입력해주세요.")
            elif normalized in {"종료", "리셋", "초기화"}:
                self.game.reset()
                message = f"{display_name}님이 바보 라이어게임을 종료했습니다."
            elif normalized in {"새게임", "새 게임"}:
                message = self.game.restart_with_same_players()
            elif normalized in {"랭킹", "순위", "ranking"}:
                message = self.stats_store.fool_liar_ranking_text() if self.stats_store else "전적 저장소가 설정되어 있지 않습니다."
            elif normalized in {"전체랭킹", "통합랭킹"}:
                message = self.stats_store.overall_ranking_text() if self.stats_store else "전적 저장소가 설정되어 있지 않습니다."
            elif normalized in {"전적", "내전적", "기록", "record"}:
                message = self.stats_store.fool_liar_player_record_text(person_id, display_name) if self.stats_store else "전적 저장소가 설정되어 있지 않습니다."
                private = True
                silent_public = True
            elif normalized in {"도움말", "도움", "명령어", "help"}:
                message = self._help_message()
            else:
                command = self.command_parser.parse(text)
                if command.type == CommandType.FORCE_RESET:
                    raise ValueError("강제리셋은 Webex 텍스트 명령에서만 사용할 수 있습니다.")
                raise ValueError("바보 라이어게임에서 사용할 수 없는 명령어입니다.")

            current_actor = self.game.current_actor_person_id()
            if (
                self.game.phase == FoolLiarPhase.EXPLAINING
                and current_actor
                and current_actor != previous_actor
                and not direct_messages
            ):
                direct_messages.append(self._turn_word_message(current_actor))

            self._clean_game_display_names()
            if self.stats_store and self.game.normal_finished and not self.game.stats_recorded:
                self.stats_store.record_fool_liar_game(self.game)

            return {
                "ok": True,
                "message": message,
                "status": self.game.status(),
                "private": private,
                "public_message": None,
                "silent_public": silent_public,
                "deal_private_cards": False,
                "direct_messages": direct_messages,
                "abort_on_dm_failure": abort_on_dm_failure,
            }
        except Exception as error:
            return {"ok": False, "message": str(error)}

    def timeout_result(self) -> GameResponse:
        self._clean_game_display_names()
        previous_actor = self.game.current_actor_person_id()
        message = self.game.handle_timeout()
        direct_messages = []
        current_actor = self.game.current_actor_person_id()
        if self.game.phase == FoolLiarPhase.EXPLAINING and current_actor != previous_actor:
            direct_messages.append(self._turn_word_message(current_actor))
        self._clean_game_display_names()
        if self.stats_store and self.game.normal_finished and not self.game.stats_recorded:
            self.stats_store.record_fool_liar_game(self.game)
        return {
            "ok": True,
            "message": message,
            "status": self.game.status(),
            "private": False,
            "silent_public": False,
            "deal_private_cards": False,
            "direct_messages": direct_messages,
        }

    def _turn_word_message(self, person_id: str) -> dict:
        return {
            "person_id": person_id,
            "message": f"설명 차례입니다.\n{self.game.personal_word(person_id)}\n60초 안에 설명을 제출해주세요.",
        }

    @staticmethod
    def _clean_display_name(display_name: str | None) -> str:
        return clean_display_name(display_name)

    def _clean_game_display_names(self) -> None:
        for player in self.game.players:
            player.display_name = clean_display_name(player.display_name)

        for description in self.game.descriptions:
            display_name = description.get("display_name")
            if isinstance(display_name, str):
                description["display_name"] = clean_display_name(display_name)

    @staticmethod
    def _help_message() -> str:
        return (
            "바보 라이어게임 도움말\n\n"
            "게임 선택: @FSS 게임선택 바보라이어게임\n"
            "다른 게임: @FSS 게임선택 홀덤 / @FSS 게임선택 주사위 / @FSS 게임선택 검키우기\n\n"
            "모집: 참가 / 참가취소 / 시작 / 종료\n"
            "진행: 제시어 / 설명 설명내용 / 투표 참가자명 / 정답 제시어\n"
            "조회: 상태 / 랭킹 / 전체랭킹 / 전적\n"
            "제시어와 역할은 공개방에 표시되지 않으며 제시어만 개인 메시지로 전달됩니다."
        )
