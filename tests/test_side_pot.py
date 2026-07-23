from app.domain.card import Card, Rank, Suit
from app.domain.game import GamePhase, HoldemGame


def card(rank: Rank, suit: Suit) -> Card:
    return Card(rank=rank, suit=suit)


def set_board(game: HoldemGame) -> None:
    game.community_cards = []

    # deck.draw()는 pop()이라서 실제 보드는 아래 역순으로 깔림
    # 실제 보드: [7♣️] [5♥️] [4♠️] [3♦️] [2♣️]
    game.deck.cards = [
        card(Rank.TWO, Suit.CLUB),
        card(Rank.THREE, Suit.DIAMOND),
        card(Rank.FOUR, Suit.SPADE),
        card(Rank.FIVE, Suit.HEART),
        card(Rank.SEVEN, Suit.CLUB),
    ]


def eliminated_ids(game: HoldemGame) -> set[str]:
    return {
        player["person_id"]
        for player in game.eliminated_players
    }


def chips_by_player(game: HoldemGame) -> dict[str, int]:
    return {
        player.person_id: player.chips
        for player in game.players
    }


def test_short_stack_best_hand_wins_only_main_pot_and_second_best_wins_side_pot():
    game = HoldemGame()

    game.join("user-1", "숏스택")
    game.join("user-2", "미들스택")
    game.join("user-3", "빅스택")

    game.players[0].chips = 1000
    game.players[1].chips = 3000
    game.players[2].chips = 10000

    game.start()

    game.players[0].hole_cards = [
        card(Rank.ACE, Suit.SPADE),
        card(Rank.ACE, Suit.HEART),
    ]

    game.players[1].hole_cards = [
        card(Rank.KING, Suit.SPADE),
        card(Rank.KING, Suit.HEART),
    ]

    game.players[2].hole_cards = [
        card(Rank.QUEEN, Suit.SPADE),
        card(Rank.QUEEN, Suit.HEART),
    ]

    set_board(game)

    message = game.all_in("user-1")
    assert "숏스택님이 1000칩 올인했습니다" in message

    message = game.all_in("user-2")
    assert "미들스택님이 2900칩 올인했습니다" in message

    message = game.call("user-3")

    assert game.phase == GamePhase.FINISHED
    assert game.game_over is False

    assert "쇼다운 결과" in message
    assert "승자: 숏스택" in message
    assert "메인팟 3000칩: 숏스택" in message
    assert "사이드팟 1 4000칩: 미들스택" in message

    chips = chips_by_player(game)

    assert chips["user-1"] == 3000
    assert chips["user-2"] == 4000
    assert chips["user-3"] == 7000


def test_short_stack_loses_main_pot_and_is_eliminated_but_side_pot_is_separate():
    game = HoldemGame()

    game.join("user-1", "숏스택")
    game.join("user-2", "미들스택")
    game.join("user-3", "빅스택")

    game.players[0].chips = 1000
    game.players[1].chips = 3000
    game.players[2].chips = 10000

    game.start()

    game.players[0].hole_cards = [
        card(Rank.QUEEN, Suit.SPADE),
        card(Rank.QUEEN, Suit.HEART),
    ]

    game.players[1].hole_cards = [
        card(Rank.ACE, Suit.SPADE),
        card(Rank.ACE, Suit.HEART),
    ]

    game.players[2].hole_cards = [
        card(Rank.KING, Suit.SPADE),
        card(Rank.KING, Suit.HEART),
    ]

    set_board(game)

    game.all_in("user-1")
    game.all_in("user-2")
    message = game.call("user-3")

    assert "메인팟 3000칩: 미들스택" in message
    assert "사이드팟 1 4000칩: 미들스택" in message
    assert "탈락: 숏스택" in message

    chips = chips_by_player(game)

    assert "user-1" not in chips
    assert chips["user-2"] == 7000
    assert chips["user-3"] == 7000

    assert eliminated_ids(game) == {"user-1"}


def test_folded_player_contributes_to_pot_but_cannot_win_any_pot():
    game = HoldemGame()

    game.join("user-1", "A")
    game.join("user-2", "B")
    game.join("user-3", "C")
    game.join("user-4", "D")

    game.players[0].chips = 1000
    game.players[1].chips = 3000
    game.players[2].chips = 3000
    game.players[3].chips = 10000

    game.start()

    # 4명 프리플랍 순서:
    # D -> A -> B -> C -> D
    #
    # D는 200칩 콜로 팟에 기여한 뒤 나중에 폴드한다.
    # D가 가장 좋은 패를 가지고 있어도 폴드했으므로 어떤 팟도 이길 수 없다.
    game.call("user-4")

    game.players[0].hole_cards = [
        card(Rank.KING, Suit.SPADE),
        card(Rank.KING, Suit.HEART),
    ]

    game.players[1].hole_cards = [
        card(Rank.QUEEN, Suit.SPADE),
        card(Rank.QUEEN, Suit.HEART),
    ]

    game.players[2].hole_cards = [
        card(Rank.JACK, Suit.SPADE),
        card(Rank.JACK, Suit.HEART),
    ]

    game.players[3].hole_cards = [
        card(Rank.ACE, Suit.SPADE),
        card(Rank.ACE, Suit.HEART),
    ]

    set_board(game)

    game.all_in("user-1")
    game.all_in("user-2")
    game.call("user-3")
    message = game.fold("user-4")

    assert "쇼다운 결과" in message
    assert "승자: A" in message

    assert "메인팟 800칩: A" in message
    assert "사이드팟 1 2400칩: A" in message
    assert "사이드팟 2 4000칩: B" in message

    chips = chips_by_player(game)

    assert chips["user-1"] == 3200
    assert chips["user-2"] == 4000
    assert "user-3" not in chips
    assert chips["user-4"] == 9800

    assert eliminated_ids(game) == {"user-3"}


def test_single_player_side_pot_returns_uncalled_extra_to_bigger_stack():
    game = HoldemGame()

    game.join("user-1", "숏스택")
    game.join("user-2", "빅스택")

    game.players[0].chips = 1000
    game.players[1].chips = 3000

    game.start()

    game.players[0].hole_cards = [
        card(Rank.ACE, Suit.SPADE),
        card(Rank.ACE, Suit.HEART),
    ]

    game.players[1].hole_cards = [
        card(Rank.KING, Suit.SPADE),
        card(Rank.KING, Suit.HEART),
    ]

    set_board(game)

    game.all_in("user-1")
    message = game.all_in("user-2")

    assert "메인팟 2000칩: 숏스택" in message
    assert "사이드팟 1 2000칩: 빅스택" in message

    chips = chips_by_player(game)

    assert chips["user-1"] == 2000
    assert chips["user-2"] == 2000
    assert game.game_over is False


def test_multiple_side_pot_levels_are_paid_to_each_eligible_best_hand():
    game = HoldemGame()

    game.join("user-1", "A")
    game.join("user-2", "B")
    game.join("user-3", "C")
    game.join("user-4", "D")

    game.players[0].chips = 1000
    game.players[1].chips = 3000
    game.players[2].chips = 6000
    game.players[3].chips = 10000

    game.start()

    game.players[0].hole_cards = [
        card(Rank.ACE, Suit.SPADE),
        card(Rank.ACE, Suit.HEART),
    ]

    game.players[1].hole_cards = [
        card(Rank.KING, Suit.SPADE),
        card(Rank.KING, Suit.HEART),
    ]

    game.players[2].hole_cards = [
        card(Rank.QUEEN, Suit.SPADE),
        card(Rank.QUEEN, Suit.HEART),
    ]

    game.players[3].hole_cards = [
        card(Rank.JACK, Suit.SPADE),
        card(Rank.JACK, Suit.HEART),
    ]

    set_board(game)

    game.all_in("user-4")
    game.all_in("user-1")
    game.all_in("user-2")
    message = game.all_in("user-3")

    assert "메인팟 4000칩: A" in message
    assert "사이드팟 1 6000칩: B" in message
    assert "사이드팟 2 6000칩: C" in message
    assert "사이드팟 3 4000칩: D" in message

    chips = chips_by_player(game)

    assert chips["user-1"] == 4000
    assert chips["user-2"] == 6000
    assert chips["user-3"] == 6000
    assert chips["user-4"] == 4000