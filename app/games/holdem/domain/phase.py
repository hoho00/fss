from enum import Enum


class GamePhase(str, Enum):
    WAITING = "WAITING"
    PRE_FLOP = "PRE_FLOP"
    FLOP = "FLOP"
    TURN = "TURN"
    RIVER = "RIVER"
    FINISHED = "FINISHED"
