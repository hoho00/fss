from app.domain.game import HoldemGame


def prepare_two_player_game() -> HoldemGame:
    game = HoldemGame()

    game.join("user-1", "상현")
    game.join("user-2", "철수")
    game.start()

    return game


def test_all_in_raise_over_minimum_updates_min_raise_to_raise_size():
    game = prepare_two_player_game()

    # 시작 직후 2인 프리플랍:
    # 상현 D/SB: 현재 베팅 100, 남은 칩 9900
    # 철수 BB: 현재 베팅 200
    # 현재 최고 베팅 200
    # 최소 레이즈 100
    assert game.current_highest_bet == 200
    assert game.min_raise == 100

    message = game.all_in("user-1")

    assert "상현님이 9900칩 올인했습니다" in message

    # 상현 총 베팅: 10000
    # 기존 최고 베팅: 200
    # 올인으로 올라간 레이즈 크기: 10000 - 200 = 9800
    # 9800 >= 최소 레이즈 100 이므로 정식 레이즈로 인정
    assert game.current_highest_bet == 10000
    assert game.min_raise == 9800

    # 철수가 콜하려면 9800칩 필요
    철수 = game.players[1]
    assert game.current_highest_bet - 철수.current_bet == 9800


def test_all_in_raise_under_minimum_updates_highest_bet_but_keeps_min_raise():
    game = prepare_two_player_game()

    # 상현은 SB 100을 이미 낸 상태.
    # 남은 칩을 150으로 강제 조정해서
    # 올인 총 베팅이 250이 되게 만든다.
    #
    # 기존 최고 베팅: 200
    # 올인 후 총 베팅: 250
    # 레이즈 크기: 250 - 200 = 50
    # 최소 레이즈 100보다 작으므로 정식 레이즈 아님
    game.players[0].chips = 150

    assert game.players[0].current_bet == 100
    assert game.current_highest_bet == 200
    assert game.min_raise == 100

    message = game.all_in("user-1")

    assert "상현님이 150칩 올인했습니다" in message

    assert game.current_highest_bet == 250
    assert game.min_raise == 100

    # 철수는 50칩만 콜하면 된다.
    철수 = game.players[1]
    assert game.current_highest_bet - 철수.current_bet == 50


def test_all_in_call_below_current_highest_bet_does_not_change_min_raise_or_highest_bet():
    game = prepare_two_player_game()

    # 상현은 SB 100을 낸 상태.
    # 남은 칩을 50으로 만들면 올인 총 베팅은 150.
    # 현재 최고 베팅 200보다 낮으므로 그냥 부족 올인 콜이다.
    game.players[0].chips = 50

    assert game.players[0].current_bet == 100
    assert game.current_highest_bet == 200
    assert game.min_raise == 100

    message = game.all_in("user-1")

    assert "상현님이 50칩 올인했습니다" in message

    assert game.current_highest_bet == 200
    assert game.min_raise == 100

    # 철수는 이미 BB 200이므로 추가 콜 금액이 없다.
    철수 = game.players[1]
    assert game.current_highest_bet - 철수.current_bet == 0


def test_after_large_all_in_raise_smaller_raise_is_rejected_by_updated_min_raise():
    game = prepare_two_player_game()

    # 철수가 실제로 재레이즈 가능한 충분한 칩을 가진 상황으로 만든다.
    # 그래야 "보유 칩 부족"이 아니라 "최소 레이즈 부족"을 검증할 수 있다.
    game.players[1].chips = 30000

    game.all_in("user-1")

    assert game.current_highest_bet == 10000
    assert game.min_raise == 9800

    # 철수가 레이즈하려면 최소:
    # 현재 최고 베팅 10000 + 최소 레이즈 9800 = 19800
    #
    # 10100은 100만 올리는 거라 실패해야 한다.
    try:
        game.raise_to("user-2", 10100)
        assert False, "최소 레이즈보다 작은 레이즈가 성공하면 안 됩니다."
    except ValueError as e:
        assert "최소 레이즈 금액은 9800칩입니다" in str(e)

    # 19800은 정확히 최소 레이즈 조건을 만족하므로 성공해야 한다.
    message = game.raise_to("user-2", 19800)

    assert "철수님이 19800칩으로 레이즈했습니다" in message
    assert game.current_highest_bet == 19800
    assert game.min_raise == 9800


def test_after_under_minimum_all_in_raise_next_min_raise_still_uses_previous_min_raise():
    game = prepare_two_player_game()

    game.players[0].chips = 150

    game.all_in("user-1")

    assert game.current_highest_bet == 250
    assert game.min_raise == 100

    # 철수는 현재 200 베팅 상태.
    # 현재 최고 베팅은 250.
    # 최소 레이즈는 그대로 100.
    #
    # 따라서 정식 레이즈 최소 총액은 350.
    # 300은 50만 올리는 거라 실패해야 한다.
    try:
        game.raise_to("user-2", 300)
        assert False, "최소 레이즈보다 작은 레이즈가 성공하면 안 됩니다."
    except ValueError as e:
        assert "최소 레이즈 금액은 100칩입니다" in str(e)

    # 350은 성공해야 한다.
    message = game.raise_to("user-2", 350)

    assert "철수님이 350칩으로 레이즈했습니다" in message
    assert game.current_highest_bet == 350
    assert game.min_raise == 100