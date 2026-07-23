from app.commands.command import BotCommand, CommandType


class CommandParser:
    def parse(self, text: str) -> BotCommand:
        normalized = self.normalize(text)

        if normalized == "참가":
            return BotCommand(CommandType.JOIN)
        if normalized == "시작":
            return BotCommand(CommandType.START)
        if normalized == "상태":
            return BotCommand(CommandType.STATUS)
        if normalized == "내카드":
            return BotCommand(CommandType.MY_CARDS)
        if normalized == "콜":
            return BotCommand(CommandType.CALL)
        if normalized == "체크":
            return BotCommand(CommandType.CHECK)
        if normalized == "폴드":
            return BotCommand(CommandType.FOLD)
        if normalized == "올인":
            return BotCommand(CommandType.ALL_IN)
        if normalized in ["도움말", "도움", "명령어", "help"]:
            return BotCommand(CommandType.HELP)
        if normalized in ["리셋", "초기화", "reset"]:
            return BotCommand(CommandType.RESET)
        if normalized in ["랭킹", "순위", "ranking"]:
            return BotCommand(CommandType.RANKING)
        if normalized in ["전체랭킹", "통합랭킹", "overall ranking"]:
            return BotCommand(CommandType.OVERALL_RANKING)
        if normalized in ["전적", "내전적", "기록", "record"]:
            return BotCommand(CommandType.RECORD)
        if normalized in ["새게임", "새 게임", "새토너먼트", "새 토너먼트"]:
            return BotCommand(CommandType.NEW_TOURNAMENT)
        if normalized == "강제리셋":
            return BotCommand(CommandType.FORCE_RESET)

        if normalized.startswith("레이즈"):
            parts = normalized.split()
            if len(parts) != 2:
                raise ValueError("사용법: 레이즈 600")
            try:
                amount = int(parts[1])
            except ValueError:
                raise ValueError("레이즈 금액은 숫자로 입력해야 합니다.")
            return BotCommand(CommandType.RAISE, amount)

        raise ValueError(
            "알 수 없는 명령어입니다. "
            "사용 가능: 참가 / 시작 / 상태 / 내카드 / 콜 / 체크 / 폴드 / 올인 / "
            "레이즈 600 / 도움말 / 리셋 / 랭킹 / 전적 / 새게임 / 강제리셋"
        )

    def normalize(self, text: str) -> str:
        normalized = text.strip()
        for prefix in ["@fss", "fss"]:
            if normalized.casefold().startswith(prefix + " "):
                return normalized[len(prefix):].strip()

        command, separator, argument = normalized.partition(" ")
        if not separator:
            return command.casefold()
        return f"{command.casefold()} {argument}"

    def _normalize(self, text: str) -> str:
        return self.normalize(text)
