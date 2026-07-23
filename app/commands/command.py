from dataclasses import dataclass
from enum import Enum


class CommandType(str, Enum):
    JOIN = "JOIN"
    START = "START"
    STATUS = "STATUS"
    MY_CARDS = "MY_CARDS"
    CALL = "CALL"
    CHECK = "CHECK"
    FOLD = "FOLD"
    RAISE = "RAISE"
    ALL_IN = "ALL_IN"
    HELP = "HELP"
    RESET = "RESET"
    RANKING = "RANKING"
    OVERALL_RANKING = "OVERALL_RANKING"
    RECORD = "RECORD"
    NEW_TOURNAMENT = "NEW_TOURNAMENT"
    FORCE_RESET = "FORCE_RESET"


@dataclass(frozen=True)
class BotCommand:
    type: CommandType
    amount: int = 0
