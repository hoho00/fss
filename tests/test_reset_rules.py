import pytest

from app.domain.game import GamePhase, HoldemGame


def test_reset_is_allowed_while_waiting():
    game = HoldemGame()
    game.join("user-1", "상현")

    message = game.reset()

    assert message == "게임을 리셋했습니다."
    assert game.phase == GamePhase.WAITING
    assert game.players == []
    assert game.pot == 0
    assert game.game_over is False


def test_reset_is_blocked_during_preflop():
    game = HoldemGame()
    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.start()

    with pytest.raises(ValueError) as error:
        game.reset()

    assert "게임 진행 중에는 리셋할 수 없습니다" in str(error.value)


def test_reset_is_blocked_during_flop():
    game = HoldemGame()
    game.phase = GamePhase.FLOP

    with pytest.raises(ValueError) as error:
        game.reset()

    assert "게임 진행 중에는 리셋할 수 없습니다" in str(error.value)


def test_reset_is_blocked_during_turn():
    game = HoldemGame()
    game.phase = GamePhase.TURN

    with pytest.raises(ValueError) as error:
        game.reset()

    assert "게임 진행 중에는 리셋할 수 없습니다" in str(error.value)


def test_reset_is_blocked_during_river():
    game = HoldemGame()
    game.phase = GamePhase.RIVER

    with pytest.raises(ValueError) as error:
        game.reset()

    assert "게임 진행 중에는 리셋할 수 없습니다" in str(error.value)


def test_reset_is_allowed_after_hand_finished():
    game = HoldemGame()
    game.phase = GamePhase.FINISHED
    game.players = []

    message = game.reset()

    assert message == "게임을 리셋했습니다."
    assert game.phase == GamePhase.WAITING
    assert game.players == []


def test_reset_is_allowed_after_game_over():
    game = HoldemGame()
    game.phase = GamePhase.FINISHED
    game.game_over = True
    game.final_winner_name = "상현"

    message = game.reset()

    assert message == "게임을 리셋했습니다."
    assert game.phase == GamePhase.WAITING
    assert game.game_over is False
    assert game.final_winner_name is None