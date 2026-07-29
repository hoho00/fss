from app.commands.command import CommandType
from app.commands.parser import CommandParser
from app.core.game_response import GameResponse
from app.domain.game import HoldemGame
from app.services.stats_store import JsonStatsStore
from app.services.display_name import COMPANY_SUFFIX_PATTERN, clean_display_name


class HoldemBotService:
    COMPANY_SUFFIX_PATTERN = COMPANY_SUFFIX_PATTERN

    def __init__(
        self,
        game: HoldemGame,
        command_parser: CommandParser,
        stats_store: JsonStatsStore | None = None,
        room_id: str | None = None,
    ):
        self.game = game
        self.command_parser = command_parser
        self.stats_store = stats_store
        self.room_id = room_id or "debug-room"

    def handle_text_command(
        self,
        person_id: str,
        display_name: str,
        text: str,
    ) -> GameResponse:
        try:
            display_name = self._clean_display_name(display_name)
            self._clean_game_display_names()

            command = self.command_parser.parse(text)

            private = False
            public_message = None
            silent_public = False
            deal_private_cards = False

            was_game_over = self.game.game_over

            if command.type == CommandType.JOIN:
                message = self.game.join(
                    person_id=person_id,
                    display_name=display_name,
                )

            elif command.type == CommandType.START:
                message = self.game.start()
                deal_private_cards = True

            elif command.type == CommandType.STATUS:
                message = self.game.status()

            elif command.type == CommandType.MY_CARDS:
                message = self.game.private_cards(person_id)
                private = True
                silent_public = True

            elif command.type == CommandType.CALL:
                message = self.game.call(person_id)

            elif command.type == CommandType.CHECK:
                message = self.game.check(person_id)

            elif command.type == CommandType.FOLD:
                message = self.game.fold(person_id)

            elif command.type == CommandType.RAISE:
                message = self.game.raise_to(
                    person_id=person_id,
                    total_bet_amount=command.amount,
                )

            elif command.type == CommandType.ALL_IN:
                message = self.game.all_in(person_id)

            elif command.type == CommandType.HELP:
                message = self._help_message()

            elif command.type == CommandType.RESET:
                self.game.reset()
                message = f"{display_name}님이 게임을 리셋했습니다."

            elif (
                getattr(CommandType, "NEW_TOURNAMENT", None) is not None
                and command.type == CommandType.NEW_TOURNAMENT
            ):
                message = self.game.restart_tournament_with_same_players()
                deal_private_cards = True

            elif command.type == CommandType.FORCE_RESET:
                raise ValueError("강제리셋은 Webex 텍스트 명령에서만 사용할 수 있습니다.")

            elif command.type == CommandType.RANKING:
                if self.stats_store is None:
                    message = "전적 저장소가 설정되어 있지 않습니다."
                else:
                    message = self.stats_store.ranking_text()

            elif command.type == CommandType.OVERALL_RANKING:
                message = self.stats_store.overall_ranking_text() if self.stats_store else "전적 저장소가 설정되어 있지 않습니다."

            elif command.type == CommandType.RECORD:
                if self.stats_store is None:
                    message = "전적 저장소가 설정되어 있지 않습니다."
                else:
                    message = self.stats_store.player_record_text(
                        person_id=person_id,
                        display_name=display_name,
                    )
                private = True
                silent_public = True

            else:
                raise ValueError("처리하지 않은 명령어입니다.")

            self._clean_game_display_names()

            if (
                self.stats_store is not None
                and not was_game_over
                and self.game.game_over
            ):
                self.stats_store.record_game_over(game=self.game)

            return {
                "ok": True,
                "message": message,
                "status": self.game.status(),
                "private": private,
                "public_message": public_message,
                "silent_public": silent_public,
                "deal_private_cards": deal_private_cards,
            }

        except Exception as e:
            return {
                "ok": False,
                "message": str(e),
            }

    def _help_message(self) -> str:
        return """
사용 가능 명령어

게임 선택:
- @FSS 게임선택 홀덤
- @FSS 게임선택 주사위
- @FSS 게임선택 바보라이어게임
- @FSS 게임선택 검키우기
- 게임 대기 또는 종료 상태에서만 게임을 바꿀 수 있습니다.

기본:
- 참가
- 시작
- 상태
- 내카드
- 도움말
- 리셋
- 새게임
- 랭킹
- 전적
- @FSS 랭킹리셋 (관리자 전용)

액션:
- 체크
- 콜
- 폴드
- 올인
- 레이즈 600

예시:
- @FSS 참가
- @FSS 시작
- @FSS 내카드
- @FSS 레이즈 600
- @FSS 올인
- @FSS 새게임
- @FSS 랭킹
- @FSS 전적
- @FSS 리셋
- @FSS 랭킹리셋 (관리자 전용)
- @FSS 게임선택 주사위
- @FSS 게임선택 바보라이어게임
- @FSS 게임선택 검키우기
""".strip()

    def _clean_display_name(self, display_name: str | None) -> str:
        return clean_display_name(display_name)

    def _clean_game_display_names(self) -> None:
        for player in self.game.players:
            player.display_name = self._clean_display_name(player.display_name)

        for eliminated_player in self.game.eliminated_players:
            display_name = eliminated_player.get("display_name")

            if isinstance(display_name, str):
                eliminated_player["display_name"] = self._clean_display_name(
                    display_name
                )

        if self.game.final_winner_name:
            self.game.final_winner_name = self._clean_display_name(
                self.game.final_winner_name
            )
