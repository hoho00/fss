import app.main as main_module
from app.domain.game import HoldemGame
from app.games.dice.domain.game import DiceGame
from app.games.fool_liar.domain.game import FoolLiarGame


def action_titles(actions):
    return [
        title
        for title, command in actions
    ]


def action_commands(actions):
    return [
        command
        for title, command in actions
    ]


def prepare_two_player_game():
    game = HoldemGame()

    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.start()

    return game


def test_waiting_game_shows_lobby_buttons():
    game = HoldemGame()

    actions = main_module._build_available_card_actions(game)

    assert action_titles(actions) == [
        "참가",
        "시작",
        "상태",
        "랭킹",
        "전적",
        "도움말",
        "리셋",
        "🎲 주사위",
        "🃏 바보 라이어",
        "개인 패효율",
        "패효율 대결",
    ]


def test_each_waiting_game_shows_other_game_shortcuts():
    holdem_commands = action_commands(main_module._build_available_card_actions(HoldemGame()))
    dice_commands = action_commands(main_module._build_available_card_actions(DiceGame()))
    fool_liar_commands = action_commands(main_module._build_available_card_actions(FoolLiarGame()))

    assert "게임선택 주사위" in holdem_commands
    assert "게임선택 바보라이어게임" in holdem_commands
    assert "게임선택 홀덤" in dice_commands
    assert "게임선택 바보라이어게임" in dice_commands
    assert "게임선택 홀덤" in fool_liar_commands
    assert "게임선택 주사위" in fool_liar_commands


def test_preflop_first_turn_shows_call_button():
    game = prepare_two_player_game()

    actions = main_module._build_available_card_actions(game)

    titles = action_titles(actions)
    commands = action_commands(actions)

    assert "상태" in titles
    assert "내카드" in titles
    assert "콜 +100" in titles
    assert "폴드" in titles
    assert "올인" in titles

    assert "레이즈 +100" in titles
    assert "레이즈 +300" in titles
    assert "레이즈 +500" in titles
    assert "레이즈 +1000" in titles

    assert "레이즈 300" in commands
    assert "레이즈 500" in commands
    assert "레이즈 700" in commands
    assert "레이즈 1200" in commands

    assert "랭킹" not in titles
    assert "전적" not in titles


def test_after_small_blind_call_big_blind_shows_check_button():
    game = prepare_two_player_game()

    game.call("user-1")

    actions = main_module._build_available_card_actions(game)

    titles = action_titles(actions)

    assert "체크 +0" in titles
    assert "콜 +100" not in titles
    assert "콜 100" not in titles

    assert "랭킹" not in titles
    assert "전적" not in titles


def test_finished_game_shows_next_hand_buttons():
    game = prepare_two_player_game()

    game.fold("user-1")

    actions = main_module._build_available_card_actions(game)

    assert action_titles(actions) == [
        "시작",
        "상태",
        "도움말",
        "리셋",
        "개인 패효율",
        "패효율 대결",
    ]


def test_game_over_shows_new_game_buttons():
    game = HoldemGame()

    game.game_over = True
    game.final_winner_name = "상현"

    actions = main_module._build_available_card_actions(game)

    assert action_titles(actions) == [
        "상태",
        "새게임",
        "리셋",
        "랭킹",
        "전적",
        "개인 패효율",
        "패효율 대결",
    ]



def test_out_of_turn_action_is_silently_ignored():
    result = {
        "ok": False,
        "message": "현재 차례는 상현님입니다.",
    }

    assert main_module._should_silently_ignore_result("콜", result) is True
    assert main_module._should_silently_ignore_result("@FSS 콜", result) is True
    assert main_module._should_silently_ignore_result("체크", result) is True
    assert main_module._should_silently_ignore_result("@FSS 폴드", result) is True
    assert main_module._should_silently_ignore_result("올인", result) is True
    assert main_module._should_silently_ignore_result("@FSS 레이즈 500", result) is True


def test_non_turn_action_error_is_not_silently_ignored():
    result = {
        "ok": False,
        "message": "게임 진행 중에는 리셋할 수 없습니다.",
    }

    assert main_module._should_silently_ignore_result(
        command_text="리셋",
        result=result,
    ) is False


def test_turn_action_other_error_is_not_silently_ignored():
    result = {
        "ok": False,
        "message": "콜할 금액이 없습니다. 체크해야 합니다.",
    }

    assert main_module._should_silently_ignore_result(
        command_text="콜",
        result=result,
    ) is False
