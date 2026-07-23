import pytest

from app.domain.card import Card, Rank, Suit
from app.domain.game import GamePhase, HoldemGame


RUNNING_PHASES = [
    GamePhase.PRE_FLOP,
    GamePhase.FLOP,
    GamePhase.TURN,
    GamePhase.RIVER,
]


PLAYER_NAMES = [
    "상현",
    "철수",
    "민수",
    "영희",
    "지훈",
    "수진",
]


def join_players(game: HoldemGame, count: int) -> None:
    for index in range(count):
        game.join(
            person_id=f"user-{index + 1}",
            display_name=PLAYER_NAMES[index],
        )


def player_ids(game: HoldemGame) -> list[str]:
    return [
        player.person_id
        for player in game.players
    ]


def eliminated_ids(game: HoldemGame) -> set[str]:
    return {
        eliminated_player["person_id"]
        for eliminated_player in game.eliminated_players
    }


def active_not_folded_count(game: HoldemGame) -> int:
    return len(
        [
            player
            for player in game.players
            if not player.folded
        ]
    )


def make_card(rank: Rank, suit: Suit) -> Card:
    return Card(rank=rank, suit=suit)


def set_board_for_showdown(game: HoldemGame) -> None:
    game.community_cards = []

    # deck.draw()는 pop()이라서 아래 리스트의 끝에서부터 보드에 깔린다.
    # 실제 보드: [7♣️] [5♥️] [4♠️] [3♦️] [2♣️]
    game.deck.cards = [
        make_card(Rank.TWO, Suit.CLUB),
        make_card(Rank.THREE, Suit.DIAMOND),
        make_card(Rank.FOUR, Suit.SPADE),
        make_card(Rank.FIVE, Suit.HEART),
        make_card(Rank.SEVEN, Suit.CLUB),
    ]


def set_showdown_cards_user_2_wins(game: HoldemGame) -> None:
    # user-2가 A2345 스트레이트로 승리하게 고정한다.
    # 나머지는 페어라서 user-2보다 약하다.

    fixed_cards = [
        [
            make_card(Rank.QUEEN, Suit.CLUB),
            make_card(Rank.QUEEN, Suit.DIAMOND),
        ],
        [
            make_card(Rank.ACE, Suit.SPADE),
            make_card(Rank.ACE, Suit.HEART),
        ],
        [
            make_card(Rank.KING, Suit.CLUB),
            make_card(Rank.KING, Suit.DIAMOND),
        ],
        [
            make_card(Rank.JACK, Suit.CLUB),
            make_card(Rank.JACK, Suit.DIAMOND),
        ],
        [
            make_card(Rank.TEN, Suit.CLUB),
            make_card(Rank.TEN, Suit.DIAMOND),
        ],
        [
            make_card(Rank.NINE, Suit.CLUB),
            make_card(Rank.NINE, Suit.DIAMOND),
        ],
    ]

    for index, player in enumerate(game.players):
        player.hole_cards = fixed_cards[index]

    set_board_for_showdown(game)


def assert_preflop_positions(game: HoldemGame) -> None:
    assert game.phase == GamePhase.PRE_FLOP

    player_count = len(game.players)

    assert player_count >= 2
    assert game.dealer_index is not None
    assert game.current_turn_index is not None
    assert 0 <= game.dealer_index < player_count
    assert 0 <= game.current_turn_index < player_count

    dealer_index = game.dealer_index

    if player_count == 2:
        small_blind_index = dealer_index
        big_blind_index = (dealer_index + 1) % player_count
        first_turn_index = dealer_index

    else:
        small_blind_index = (dealer_index + 1) % player_count
        big_blind_index = (dealer_index + 2) % player_count
        first_turn_index = (dealer_index + 3) % player_count

    assert game.players[small_blind_index].current_bet == game.small_blind
    assert game.players[big_blind_index].current_bet == game.big_blind
    assert game.current_turn_index == first_turn_index

    for index, player in enumerate(game.players):
        if index not in [small_blind_index, big_blind_index]:
            assert player.current_bet == 0

    current_player = game.players[game.current_turn_index]

    assert current_player.folded is False
    assert current_player.all_in is False


def assert_postflop_first_turn(game: HoldemGame) -> None:
    assert game.phase == GamePhase.FLOP

    player_count = len(game.players)
    dealer_index = game.dealer_index

    assert dealer_index is not None
    assert game.current_turn_index is not None

    expected_first_turn_index = (dealer_index + 1) % player_count

    assert game.current_turn_index == expected_first_turn_index

    current_player = game.players[game.current_turn_index]

    assert current_player.folded is False
    assert current_player.all_in is False


def assert_heads_up_rule(game: HoldemGame) -> None:
    assert len(game.players) == 2
    assert game.dealer_index is not None
    assert game.current_turn_index is not None

    dealer_index = game.dealer_index
    big_blind_index = (dealer_index + 1) % 2

    dealer = game.players[dealer_index]
    big_blind = game.players[big_blind_index]

    assert dealer.current_bet == game.small_blind
    assert big_blind.current_bet == game.big_blind
    assert game.current_turn_index == dealer_index


def advance_preflop_to_flop(game: HoldemGame) -> None:
    guard = 0

    while game.phase == GamePhase.PRE_FLOP:
        assert game.current_turn_index is not None

        current_player = game.players[game.current_turn_index]
        need_to_call = game.current_highest_bet - current_player.current_bet

        if need_to_call > 0:
            game.call(current_player.person_id)
        else:
            game.check(current_player.person_id)

        guard += 1

        if guard > 30:
            raise AssertionError("프리플랍 진행이 30회를 초과했습니다.")

    assert game.phase == GamePhase.FLOP


def finish_hand_by_folding_until_one_left(
    game: HoldemGame,
    zero_chip_player_ids: set[str] | None = None,
) -> None:
    if zero_chip_player_ids is None:
        zero_chip_player_ids = set()

    for player in game.players:
        if player.person_id in zero_chip_player_ids:
            player.chips = 0

    guard = 0

    while game.phase in RUNNING_PHASES and not game.game_over:
        assert game.current_turn_index is not None

        if active_not_folded_count(game) <= 1:
            break

        current_player = game.players[game.current_turn_index]
        game.fold(current_player.person_id)

        guard += 1

        if guard > 30:
            raise AssertionError("핸드 종료 진행이 30회를 초과했습니다.")

    assert game.phase == GamePhase.FINISHED or game.game_over


def finish_hand_with_current_player_eliminated(game: HoldemGame) -> str:
    assert game.current_turn_index is not None

    loser = game.players[game.current_turn_index]
    loser_id = loser.person_id

    finish_hand_by_folding_until_one_left(
        game=game,
        zero_chip_player_ids={loser_id},
    )

    return loser_id


@pytest.mark.parametrize("player_count", [2, 3, 4, 5, 6])
def test_preflop_blind_and_first_turn_for_2_to_6_players(player_count):
    game = HoldemGame()

    join_players(game, player_count)
    game.start()

    assert len(game.players) == player_count
    assert_preflop_positions(game)


@pytest.mark.parametrize("player_count", [2, 3, 4, 5, 6])
def test_postflop_first_turn_for_2_to_6_players(player_count):
    game = HoldemGame()

    join_players(game, player_count)
    game.start()

    advance_preflop_to_flop(game)

    assert_postflop_first_turn(game)


@pytest.mark.parametrize("player_count", [2, 3, 4, 5, 6])
def test_dealer_rotates_after_normal_finished_hand_without_elimination(player_count):
    game = HoldemGame()

    join_players(game, player_count)
    game.start()

    old_dealer_index = game.dealer_index
    assert old_dealer_index is not None

    expected_next_dealer_id = game.players[
        (old_dealer_index + 1) % player_count
    ].person_id

    finish_hand_by_folding_until_one_left(game)

    assert game.phase == GamePhase.FINISHED
    assert game.game_over is False
    assert len(game.players) == player_count

    game.start()

    assert game.players[game.dealer_index].person_id == expected_next_dealer_id
    assert_preflop_positions(game)


def test_elimination_chain_6_to_5_to_4_to_3_to_2_to_1():
    game = HoldemGame()

    join_players(game, 6)
    game.start()

    all_eliminated_ids = set()

    for expected_player_count in [6, 5, 4, 3, 2]:
        assert len(game.players) == expected_player_count
        assert_preflop_positions(game)

        loser_id = finish_hand_with_current_player_eliminated(game)

        all_eliminated_ids.add(loser_id)

        assert loser_id not in player_ids(game)
        assert all_eliminated_ids.issubset(eliminated_ids(game))

        if expected_player_count > 2:
            assert game.game_over is False
            assert game.phase == GamePhase.FINISHED
            assert len(game.players) == expected_player_count - 1

            game.start()

        else:
            assert game.game_over is True
            assert len(game.players) == 1
            assert game.final_winner_name == game.players[0].display_name


def test_transition_from_three_players_to_heads_up_uses_heads_up_rule():
    game = HoldemGame()

    join_players(game, 3)
    game.start()

    assert len(game.players) == 3
    assert_preflop_positions(game)

    loser_id = finish_hand_with_current_player_eliminated(game)

    assert loser_id not in player_ids(game)
    assert len(game.players) == 2
    assert game.game_over is False
    assert game.phase == GamePhase.FINISHED

    game.start()

    assert_heads_up_rule(game)


def test_two_player_elimination_ends_entire_game():
    game = HoldemGame()

    join_players(game, 2)
    game.start()

    loser_id = finish_hand_with_current_player_eliminated(game)

    assert loser_id not in player_ids(game)
    assert len(game.players) == 1
    assert game.game_over is True
    assert game.final_winner_name == game.players[0].display_name

    with pytest.raises(ValueError) as error:
        game.start()

    assert "게임이 종료되었습니다" in str(error.value)


def test_folded_player_never_gets_current_turn_after_fold():
    game = HoldemGame()

    join_players(game, 6)
    game.start()

    assert game.current_turn_index is not None

    first_player = game.players[game.current_turn_index]
    game.fold(first_player.person_id)

    assert game.phase == GamePhase.PRE_FLOP
    assert game.current_turn_index is not None

    current_player = game.players[game.current_turn_index]

    assert current_player.person_id != first_player.person_id
    assert current_player.folded is False


def test_every_next_hand_after_elimination_has_valid_blinds():
    game = HoldemGame()

    join_players(game, 6)
    game.start()

    while len(game.players) > 2:
        assert_preflop_positions(game)

        loser_id = finish_hand_with_current_player_eliminated(game)

        assert loser_id not in player_ids(game)
        assert game.phase == GamePhase.FINISHED
        assert game.game_over is False

        game.start()

        assert_preflop_positions(game)


def test_eliminated_player_does_not_come_back_after_next_start():
    game = HoldemGame()

    join_players(game, 4)
    game.start()

    loser_id = finish_hand_with_current_player_eliminated(game)

    assert loser_id not in player_ids(game)

    game.start()

    assert loser_id not in player_ids(game)
    assert len(game.players) == 3
    assert_preflop_positions(game)


def test_two_players_eliminated_same_hand_and_game_continues_heads_up():
    game = HoldemGame()

    join_players(game, 4)
    game.start()

    set_showdown_cards_user_2_wins(game)

    # 4명 프리플랍 순서:
    # user-4 -> user-1 -> user-2 -> user-3
    #
    # user-4, user-1 올인
    # user-2 콜 후 쇼다운 승리
    # user-3 폴드 후 생존
    game.all_in("user-4")
    game.all_in("user-1")
    game.call("user-2")
    game.fold("user-3")

    assert game.phase == GamePhase.FINISHED
    assert game.game_over is False

    assert {"user-4", "user-1"}.issubset(eliminated_ids(game))

    assert "user-4" not in player_ids(game)
    assert "user-1" not in player_ids(game)

    assert len(game.players) == 2
    assert set(player_ids(game)) == {"user-2", "user-3"}

    game.start()

    assert_heads_up_rule(game)


def test_three_players_eliminated_same_hand_and_game_continues_heads_up():
    game = HoldemGame()

    join_players(game, 5)
    game.start()

    set_showdown_cards_user_2_wins(game)

    # 5명 프리플랍 순서:
    # user-4 -> user-5 -> user-1 -> user-2 -> user-3
    #
    # user-4, user-5, user-1 올인
    # user-2 콜 후 쇼다운 승리
    # user-3 폴드 후 생존
    game.all_in("user-4")
    game.all_in("user-5")
    game.all_in("user-1")
    game.call("user-2")
    game.fold("user-3")

    assert game.phase == GamePhase.FINISHED
    assert game.game_over is False

    assert {"user-4", "user-5", "user-1"}.issubset(eliminated_ids(game))

    assert "user-4" not in player_ids(game)
    assert "user-5" not in player_ids(game)
    assert "user-1" not in player_ids(game)

    assert len(game.players) == 2
    assert set(player_ids(game)) == {"user-2", "user-3"}

    game.start()

    assert_heads_up_rule(game)


def test_three_players_eliminated_same_hand_and_game_over():
    game = HoldemGame()

    join_players(game, 4)
    game.start()

    set_showdown_cards_user_2_wins(game)

    # 4명 프리플랍 순서:
    # user-4 -> user-1 -> user-2 -> user-3
    #
    # user-2가 승리하고 나머지 3명은 올인 패배로 동시 탈락
    game.all_in("user-4")
    game.all_in("user-1")
    game.call("user-2")
    game.call("user-3")

    assert game.game_over is True
    assert len(game.players) == 1
    assert game.players[0].person_id == "user-2"
    assert game.final_winner_name == game.players[0].display_name

    assert {"user-4", "user-1", "user-3"}.issubset(eliminated_ids(game))
    assert len(game.eliminated_players) == 3

    with pytest.raises(ValueError) as error:
        game.start()

    assert "게임이 종료되었습니다" in str(error.value)


def test_two_players_eliminated_same_hand_from_six_players_continues_with_four():
    game = HoldemGame()

    join_players(game, 6)
    game.start()

    set_showdown_cards_user_2_wins(game)

    # 6명 프리플랍 순서:
    # user-4 -> user-5 -> user-6 -> user-1 -> user-2 -> user-3
    #
    # user-4, user-5 올인 패배
    # user-2 승리
    # 나머지 user-1, user-3, user-6 생존
    game.all_in("user-4")
    game.all_in("user-5")
    game.fold("user-6")
    game.fold("user-1")
    game.call("user-2")
    game.fold("user-3")

    assert game.phase == GamePhase.FINISHED
    assert game.game_over is False

    assert {"user-4", "user-5"}.issubset(eliminated_ids(game))

    assert "user-4" not in player_ids(game)
    assert "user-5" not in player_ids(game)

    assert len(game.players) == 4
    assert set(player_ids(game)) == {
        "user-1",
        "user-2",
        "user-3",
        "user-6",
    }

    game.start()

    assert len(game.players) == 4
    assert_preflop_positions(game)


def test_three_players_eliminated_same_hand_from_six_players_continues_with_three():
    game = HoldemGame()

    join_players(game, 6)
    game.start()

    set_showdown_cards_user_2_wins(game)

    # 6명 프리플랍 순서:
    # user-4 -> user-5 -> user-6 -> user-1 -> user-2 -> user-3
    #
    # user-4, user-5, user-6 올인 패배
    # user-2 승리
    # user-1, user-3 생존
    game.all_in("user-4")
    game.all_in("user-5")
    game.all_in("user-6")
    game.fold("user-1")
    game.call("user-2")
    game.fold("user-3")

    assert game.phase == GamePhase.FINISHED
    assert game.game_over is False

    assert {"user-4", "user-5", "user-6"}.issubset(eliminated_ids(game))

    assert "user-4" not in player_ids(game)
    assert "user-5" not in player_ids(game)
    assert "user-6" not in player_ids(game)

    assert len(game.players) == 3
    assert set(player_ids(game)) == {
        "user-1",
        "user-2",
        "user-3",
    }

    game.start()

    assert len(game.players) == 3
    assert_preflop_positions(game)