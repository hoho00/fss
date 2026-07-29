from app.commands.command import CommandType
from app.commands.parser import CommandParser
from app.core.game_response import GameResponse
from app.games.dice.domain.game import DiceGame
from app.services.display_name import clean_display_name
from app.services.stats_store import JsonStatsStore


class DiceBotService:
    def __init__(
        self,
        game: DiceGame,
        command_parser: CommandParser,
        stats_store: JsonStatsStore | None = None,
    ):
        self.game = game
        self.command_parser = command_parser
        self.stats_store = stats_store

    def handle_text_command(
        self,
        person_id: str,
        display_name: str,
        text: str,
    ) -> GameResponse:
        try:
            display_name = clean_display_name(display_name)
            for player in self.game.players:
                player.display_name = clean_display_name(player.display_name)

            command = self.command_parser.parse(text)
            private = False
            silent_public = False

            if command.type == CommandType.JOIN:
                message = self.game.join(person_id, display_name)
            elif command.type in {CommandType.START, CommandType.NEW_TOURNAMENT}:
                message = self.game.start()
            elif command.type == CommandType.STATUS:
                message = self.game.status()
            elif command.type == CommandType.RANKING:
                message = (
                    self.stats_store.dice_ranking_text()
                    if self.stats_store is not None
                    else "전적 저장소가 설정되어 있지 않습니다."
                )
            elif command.type == CommandType.OVERALL_RANKING:
                message = self.stats_store.overall_ranking_text() if self.stats_store else "전적 저장소가 설정되어 있지 않습니다."
            elif command.type == CommandType.RECORD:
                message = (
                    self.stats_store.dice_player_record_text(person_id, display_name)
                    if self.stats_store is not None
                    else "전적 저장소가 설정되어 있지 않습니다."
                )
                private = True
                silent_public = True
            elif command.type == CommandType.RESET:
                self.game.reset()
                message = f"{display_name}님이 주사위 게임을 리셋했습니다."
            elif command.type == CommandType.HELP:
                message = (
                    "주사위 게임 도움말\n\n"
                    "게임 선택: @FSS 게임선택 주사위\n"
                    "진행: 참가 → 시작\n"
                    "시작하면 참가자 전원의 주사위를 굴리고, 최고 숫자가 우승합니다. "
                    "동점자는 공동 우승입니다.\n\n"
                    "명령어: 참가 / 시작 / 상태 / 새게임 / 리셋\n"
                    "홀덤으로 돌아가기: @FSS 게임선택 홀덤"
                    "\n바보 라이어게임 선택: @FSS 게임선택 바보라이어게임"
                    "\n검키우기 선택: @FSS 게임선택 검키우기"
                )
            else:
                raise ValueError("주사위 게임에서 사용할 수 없는 명령어입니다.")

            if (
                self.stats_store is not None
                and command.type in {CommandType.START, CommandType.NEW_TOURNAMENT}
                and self.game.game_over
            ):
                self.stats_store.record_dice_game(self.game)

            return {
                "ok": True,
                "message": message,
                "status": self.game.status(),
                "private": private,
                "public_message": None,
                "silent_public": silent_public,
                "deal_private_cards": False,
            }
        except Exception as error:
            return {"ok": False, "message": str(error)}
