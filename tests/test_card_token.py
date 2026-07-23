import app.main as main_module
from app.domain.game import GamePhase, HoldemGame


def reset_card_token_state():
    main_module.room_games.clear()
    main_module.latest_card_tokens.clear()


def test_latest_card_action_is_valid_only_for_latest_token():
    reset_card_token_state()

    main_module.latest_card_tokens["room-a"] = "latest-token"

    assert main_module._is_latest_card_action("room-a", "latest-token") is True
    assert main_module._is_latest_card_action("room-a", "old-token") is False
    assert main_module._is_latest_card_action("room-a", None) is False
    assert main_module._is_latest_card_action("room-b", "latest-token") is False


def test_create_latest_card_token_replaces_previous_token():
    reset_card_token_state()

    first_token = main_module._create_latest_card_token("room-a")
    second_token = main_module._create_latest_card_token("room-a")

    assert first_token != second_token
    assert main_module.latest_card_tokens["room-a"] == second_token

    assert main_module._is_latest_card_action("room-a", first_token) is False
    assert main_module._is_latest_card_action("room-a", second_token) is True


def test_stale_join_button_is_allowed_only_while_waiting():
    reset_card_token_state()

    game = HoldemGame()
    main_module.room_games["room-a"] = game

    game.phase = GamePhase.WAITING
    game.game_over = False

    assert main_module._can_accept_stale_card_action("room-a", "참가") is True

    game.phase = GamePhase.PRE_FLOP

    assert main_module._can_accept_stale_card_action("room-a", "참가") is False

    game.phase = GamePhase.FLOP

    assert main_module._can_accept_stale_card_action("room-a", "참가") is False

    game.phase = GamePhase.TURN

    assert main_module._can_accept_stale_card_action("room-a", "참가") is False

    game.phase = GamePhase.RIVER

    assert main_module._can_accept_stale_card_action("room-a", "참가") is False

    game.phase = GamePhase.WAITING
    game.game_over = True

    assert main_module._can_accept_stale_card_action("room-a", "참가") is False


def test_stale_ranking_and_record_buttons_are_allowed_only_while_waiting():
    reset_card_token_state()

    game = HoldemGame()
    main_module.room_games["room-a"] = game

    game.phase = GamePhase.WAITING
    game.game_over = False

    assert main_module._can_accept_stale_card_action("room-a", "랭킹") is True
    assert main_module._can_accept_stale_card_action("room-a", "전적") is True

    game.phase = GamePhase.PRE_FLOP

    assert main_module._can_accept_stale_card_action("room-a", "랭킹") is False
    assert main_module._can_accept_stale_card_action("room-a", "전적") is False

    game.phase = GamePhase.WAITING
    game.game_over = True

    assert main_module._can_accept_stale_card_action("room-a", "랭킹") is False
    assert main_module._can_accept_stale_card_action("room-a", "전적") is False


def test_stale_safe_read_only_buttons_are_always_allowed():
    reset_card_token_state()

    game = HoldemGame()
    main_module.room_games["room-a"] = game

    game.phase = GamePhase.PRE_FLOP

    assert main_module._can_accept_stale_card_action("room-a", "상태") is True
    assert main_module._can_accept_stale_card_action("room-a", "내카드") is True
    assert main_module._can_accept_stale_card_action("room-a", "도움말") is True

    game.phase = GamePhase.FLOP

    assert main_module._can_accept_stale_card_action("room-a", "상태") is True
    assert main_module._can_accept_stale_card_action("room-a", "내카드") is True
    assert main_module._can_accept_stale_card_action("room-a", "도움말") is True

    game.phase = GamePhase.WAITING
    game.game_over = True

    assert main_module._can_accept_stale_card_action("room-a", "상태") is True
    assert main_module._can_accept_stale_card_action("room-a", "내카드") is True
    assert main_module._can_accept_stale_card_action("room-a", "도움말") is True


def test_stale_betting_buttons_are_blocked():
    reset_card_token_state()

    game = HoldemGame()
    main_module.room_games["room-a"] = game
    game.phase = GamePhase.PRE_FLOP

    assert main_module._can_accept_stale_card_action("room-a", "콜") is False
    assert main_module._can_accept_stale_card_action("room-a", "체크") is False
    assert main_module._can_accept_stale_card_action("room-a", "폴드") is False
    assert main_module._can_accept_stale_card_action("room-a", "올인") is False
    assert main_module._can_accept_stale_card_action("room-a", "레이즈 300") is False
    assert main_module._can_accept_stale_card_action("room-a", "레이즈 500") is False
    assert main_module._can_accept_stale_card_action("room-a", "레이즈 1200") is False


def test_stale_game_control_buttons_are_blocked():
    reset_card_token_state()

    game = HoldemGame()
    main_module.room_games["room-a"] = game

    game.phase = GamePhase.WAITING

    assert main_module._can_accept_stale_card_action("room-a", "시작") is False
    assert main_module._can_accept_stale_card_action("room-a", "리셋") is False
    assert main_module._can_accept_stale_card_action("room-a", "새게임") is False

    game.phase = GamePhase.FINISHED

    assert main_module._can_accept_stale_card_action("room-a", "시작") is False
    assert main_module._can_accept_stale_card_action("room-a", "리셋") is False
    assert main_module._can_accept_stale_card_action("room-a", "새게임") is False

    game.game_over = True

    assert main_module._can_accept_stale_card_action("room-a", "시작") is False
    assert main_module._can_accept_stale_card_action("room-a", "리셋") is False
    assert main_module._can_accept_stale_card_action("room-a", "새게임") is False